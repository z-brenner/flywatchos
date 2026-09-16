// Offline evidence inventory. Run with -readOnly -noanalysis; outputs are private.
//@category Garmin

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.block.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.pcode.*;
import ghidra.program.model.symbol.Reference;
import com.google.gson.GsonBuilder;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

public class UsbDetachReport extends GhidraScript {
    private final Map<Long, Function> owners = new TreeMap<>();

    private Map<String, Object> row(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) result.put((String)pairs[i], pairs[i + 1]);
        return result;
    }

    private String digest(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    private void addOwner(Address address) {
        Function function = getFunctionContaining(address);
        if (function != null) owners.put(function.getEntryPoint().getOffset(), function);
    }

    private List<Object> references(long start, long end) throws Exception {
        List<Object> result = new ArrayList<>();
        AddressIterator destinations = currentProgram.getReferenceManager()
            .getReferenceDestinationIterator(new AddressSet(toAddr(start), toAddr(end)), true);
        while (destinations.hasNext()) {
            Address target = destinations.next();
            for (Reference reference : getReferencesTo(target)) {
                addOwner(reference.getFromAddress());
                result.add(row("from", reference.getFromAddress().getOffset(),
                    "to", target.getOffset(), "type", reference.getReferenceType().toString()));
            }
        }
        return result;
    }

    @Override public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2) throw new IllegalArgumentException("<private-json> <private-decompilation>");
        Path jsonPath = Paths.get(args[0]).toAbsolutePath().normalize();
        Path textPath = Paths.get(args[1]).toAbsolutePath().normalize();
        checkOutputs(jsonPath, textPath);
        if (!currentProgram.getName().equals("stream_01_fw_all_bin.bin"))
            throw new IllegalArgumentException("wrong program");
        Map<String, Object> report = row("schema", "flyos.fr245.usb-ghidra-inventory.v1",
            "program", currentProgram.getName(), "executable_sha256", currentProgram.getExecutableSHA256(),
            "computed_access_coverage_complete", false,
            "coverage_limit", "References and seeded high P-code do not close arbitrary aliases, external code, or dynamic observer registrations.");
        report.put("usb_references", references(0x1ffc6eecL, 0x1ffc6f80L));
        report.put("observer_references", references(0x1ffc8aa0L, 0x1ffc8abfL));
        report.put("key_references", references(0x1ffdbbc8L, 0x1ffdbce7L));
        long[] seeds = {0xf7e4, 0xfa18, 0xfa48, 0xfaa4, 0xfb34, 0xfcac, 0xfcd8,
            0x8844, 0x8b04, 0x7bdc, 0x2053c, 0x20578, 0x205e4, 0x206e0, 0x207b0,
            0x20858, 0x20a64, 0x20b20, 0x20b6c, 0x8734, 0x874c, 0x7720,
            0x1ef1c, 0x1eef0, 0x67d8, 0x5306c, 0x530cc, 0x5325c, 0x5330c, 0x53b10};
        for (long seed : seeds) addOwner(toAddr(seed));

        // Include every aligned pointer into the relevant RAM ranges and its users.
        List<Object> literals = new ArrayList<>();
        for (long at = 0x3000; at <= 0x1ffffc; at += 4) {
            long value = Integer.toUnsignedLong(currentProgram.getMemory().getInt(toAddr(at)));
            if ((value >= 0x1ffc6eecL && value <= 0x1ffc6f80L) ||
                (value >= 0x1ffc8aa0L && value <= 0x1ffc8abfL) ||
                (value >= 0x1ffdbbc8L && value <= 0x1ffdbce7L)) {
                List<Long> users = new ArrayList<>();
                for (Reference reference : getReferencesTo(toAddr(at))) {
                    users.add(reference.getFromAddress().getOffset());
                    addOwner(reference.getFromAddress());
                }
                literals.add(row("address", at, "value", value, "users", users));
            }
        }
        report.put("aligned_ram_literals", literals);

        List<Object> functions = new ArrayList<>();
        List<Object> memoryOps = new ArrayList<>();
        StringBuilder privateText = new StringBuilder();
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        try {
            for (Function function : owners.values()) {
                monitor.checkCancelled();
                AddressSetView body = function.getBody();
                List<Object> ranges = new ArrayList<>();
                MessageDigest hash = MessageDigest.getInstance("SHA-256");
                for (AddressRange range : body.getAddressRanges()) {
                    byte[] bytes = getBytes(range.getMinAddress(), (int)range.getLength());
                    hash.update(bytes);
                    ranges.add(row("start", range.getMinAddress().getOffset(),
                        "end_inclusive", range.getMaxAddress().getOffset(), "sha256", digest(bytes)));
                }
                List<Long> calls = new ArrayList<>();
                for (Function callee : function.getCalledFunctions(monitor))
                    calls.add(callee.getEntryPoint().getOffset());
                Collections.sort(calls);
                Map<String, Object> item = row("entry", function.getEntryPoint().getOffset(),
                    "ranges", ranges, "sha256", HexFormat.of().formatHex(hash.digest()), "callees", calls);
                DecompileResults result = decompiler.decompileFunction(function, 60, monitor);
                item.put("decompiled", result.decompileCompleted());
                if (result.decompileCompleted()) {
                    privateText.append("\n===== ").append(function.getEntryPoint()).append(" =====\n")
                        .append(result.getDecompiledFunction().getC());
                    Iterator<PcodeOpAST> iterator = result.getHighFunction().getPcodeOps();
                    while (iterator.hasNext()) {
                        PcodeOpAST op = iterator.next();
                        if (op.getOpcode() == PcodeOp.LOAD || op.getOpcode() == PcodeOp.STORE) {
                            Varnode pointer = op.getInput(1);
                            memoryOps.add(row("function", function.getEntryPoint().getOffset(),
                                "instruction", op.getSeqnum().getTarget().getOffset(), "operation", op.getMnemonic(),
                                "constant_pointer", pointer.isConstant() ? pointer.getOffset() : null,
                                "width", op.getOpcode() == PcodeOp.LOAD ? op.getOutput().getSize() : op.getInput(2).getSize(),
                                "unresolved_computed_pointer", !pointer.isConstant()));
                        }
                    }
                }
                functions.add(item);
            }
        } finally { decompiler.dispose(); }
        report.put("functions", functions);
        report.put("memory_operations", memoryOps);

        List<Object> blocks = new ArrayList<>();
        SimpleBlockModel model = new SimpleBlockModel(currentProgram);
        CodeBlockIterator iterator = model.getCodeBlocksContaining(
            new AddressSet(toAddr(0x20858), toAddr(0x20a3f)), monitor);
        while (iterator.hasNext()) {
            CodeBlock block = iterator.next();
            List<Object> destinations = new ArrayList<>();
            CodeBlockReferenceIterator edges = block.getDestinations(monitor);
            while (edges.hasNext()) {
                CodeBlockReference edge = edges.next();
                destinations.add(row("to", edge.getDestinationAddress().getOffset(),
                    "flow", edge.getFlowType().toString()));
            }
            blocks.add(row("start", block.getMinAddress().getOffset(),
                "end_inclusive", block.getMaxAddress().getOffset(), "destinations", destinations));
        }
        report.put("state_machine_blocks", blocks);
        String json = new GsonBuilder().setPrettyPrinting().serializeNulls().create().toJson(report) + "\n";
        checkOutputs(jsonPath, textPath);
        Files.createDirectories(jsonPath.getParent());
        Files.createDirectories(textPath.getParent());
        // Reserve both names before writing either; CREATE_NEW prevents race-time truncation.
        try (OutputStream jsonOut = Files.newOutputStream(jsonPath, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
             OutputStream textOut = Files.newOutputStream(textPath, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
            jsonOut.write(json.getBytes(StandardCharsets.UTF_8));
            textOut.write(privateText.toString().getBytes(StandardCharsets.UTF_8));
        }
        println("USB_DETACH_REPORT_COMPLETE json_sha256=" + digest(json.getBytes(StandardCharsets.UTF_8)) +
            " functions=" + functions.size() + " blocks=" + blocks.size() +
            " computed_access_coverage_complete=false");
    }

    private void checkOutputs(Path jsonPath, Path textPath) throws Exception {
        if (jsonPath.equals(textPath) ||
            Files.exists(jsonPath, LinkOption.NOFOLLOW_LINKS) ||
            Files.exists(textPath, LinkOption.NOFOLLOW_LINKS))
            throw new IllegalArgumentException("output collision: JSON and decompilation must both be new paths");
    }
}
