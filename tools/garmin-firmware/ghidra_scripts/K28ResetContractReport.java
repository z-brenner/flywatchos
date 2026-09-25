// Bounded, private startup inventory for the pinned FR245 13.70 image.
// Usage: -postScript K28ResetContractReport.java <json> <decompilation> <stage2> <depth>
//@category Garmin

import com.google.gson.GsonBuilder;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressRange;
import ghidra.program.model.address.AddressSetView;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.pcode.PcodeOpAST;
import ghidra.program.model.pcode.Varnode;
import ghidra.program.model.symbol.Reference;

import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Deque;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

public class K28ResetContractReport extends GhidraScript {
    private static final long APP_BASE = 0x00003000L;
    private static final long APP_END_EXCLUSIVE = 0x00200000L;
    private static final long RESET_HANDLER = 0x000031f0L;
    private static final String PINNED_SHA256 =
        "b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6";

    private Map<String, Object> row(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index < pairs.length; index += 2) {
            result.put((String) pairs[index], pairs[index + 1]);
        }
        return result;
    }

    private String address(long value) {
        return String.format("0x%08x", value);
    }

    private String digest(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(
            MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    private boolean isMmio(Address value) {
        long offset = value.getOffset();
        return (offset >= 0x40000000L && offset < 0x60000000L) ||
               (offset >= 0xe0000000L && offset < 0xe0100000L);
    }

    private byte[] functionBytes(Function function) throws Exception {
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        for (AddressRange range : function.getBody()) {
            int length = Math.toIntExact(range.getLength());
            byte[] bytes = new byte[length];
            int read = currentProgram.getMemory().getBytes(range.getMinAddress(), bytes);
            if (read != length) {
                throw new IllegalStateException(
                    "short function read at " + range.getMinAddress());
            }
            hash.update(bytes);
        }
        return hash.digest();
    }

    private byte[] mappedApplicationBytes() throws Exception {
        int length = Math.toIntExact(APP_END_EXCLUSIVE - APP_BASE);
        byte[] bytes = new byte[length];
        int read = currentProgram.getMemory().getBytes(toAddr(APP_BASE), bytes);
        if (read != length) {
            throw new IllegalStateException("short mapped application read: " + read);
        }
        return bytes;
    }

    private List<Long> directCalls(Function function) {
        Set<Long> calls = new TreeSet<>();
        InstructionIterator instructions = currentProgram.getListing()
            .getInstructions(function.getBody(), true);
        while (instructions.hasNext()) {
            Instruction instruction = instructions.next();
            for (Reference reference : instruction.getReferencesFrom()) {
                if (reference.getReferenceType().isCall() &&
                    reference.getToAddress().isMemoryAddress()) {
                    calls.add(reference.getToAddress().getOffset() & ~1L);
                }
            }
        }
        return new ArrayList<>(calls);
    }

    private Map<Long, Integer> closure(long stage2, int maxDepth) {
        Map<Long, Integer> depths = new TreeMap<>();
        Deque<long[]> pending = new ArrayDeque<>();
        pending.add(new long[] {RESET_HANDLER, 0});
        pending.add(new long[] {stage2, 0});
        while (!pending.isEmpty()) {
            long[] item = pending.removeFirst();
            long entry = item[0];
            int depth = (int) item[1];
            Integer known = depths.get(entry);
            if (known != null && known <= depth) {
                continue;
            }
            depths.put(entry, depth);
            Function function = getFunctionAt(toAddr(entry));
            if (function == null || depth >= maxDepth) {
                continue;
            }
            for (long callee : directCalls(function)) {
                if (callee >= APP_BASE && callee < APP_END_EXCLUSIVE) {
                    pending.addLast(new long[] {callee, depth + 1});
                }
            }
        }
        return depths;
    }

    private void checkOutputs(Path jsonPath, Path textPath) {
        if (jsonPath.equals(textPath) ||
            Files.exists(jsonPath, LinkOption.NOFOLLOW_LINKS) ||
            Files.exists(textPath, LinkOption.NOFOLLOW_LINKS)) {
            throw new IllegalArgumentException(
                "output collision: inventory and decompilation must be new paths");
        }
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 4) {
            throw new IllegalArgumentException(
                "<inventory.json> <decompilation.txt> <stage2-address> <max-depth>");
        }
        Path jsonPath = Paths.get(args[0]).toAbsolutePath().normalize();
        Path textPath = Paths.get(args[1]).toAbsolutePath().normalize();
        long stage2 = Long.decode(args[2]) & ~1L;
        int maxDepth = Integer.decode(args[3]);
        if (stage2 != 0x00019340L || maxDepth != 3) {
            throw new IllegalArgumentException("unexpected reset-contract roots or depth");
        }
        checkOutputs(jsonPath, textPath);

        String executableSha = currentProgram.getExecutableSHA256();
        if (executableSha == null ||
            !PINNED_SHA256.equals(executableSha.toLowerCase())) {
            throw new IllegalArgumentException(
                "wrong program SHA-256: " + executableSha);
        }
        if (!"stream_01_fw_all_bin.bin".equals(currentProgram.getName())) {
            throw new IllegalArgumentException("wrong program name");
        }

        Map<Long, Integer> depths = closure(stage2, maxDepth);
        int unresolvedSeeds = 0;
        for (long root : new long[] {RESET_HANDLER, stage2}) {
            if (getFunctionAt(toAddr(root)) == null) {
                unresolvedSeeds++;
            }
        }
        int unresolvedFunctions = 0;
        List<Object> functions = new ArrayList<>();
        List<Object> computedMmio = new ArrayList<>();
        List<Object> unknownMmioWidths = new ArrayList<>();
        List<Object> unknownMmioValues = new ArrayList<>();
        List<Object> unboundedPolls = new ArrayList<>();
        List<Object> unknownMemoryRanges = new ArrayList<>();
        StringBuilder privateText = new StringBuilder();

        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        try {
            for (Map.Entry<Long, Integer> closureItem : depths.entrySet()) {
                monitor.checkCancelled();
                long entry = closureItem.getKey();
                Function function = getFunctionAt(toAddr(entry));
                if (function == null) {
                    unresolvedFunctions++;
                    continue;
                }
                List<String> calls = new ArrayList<>();
                for (long callee : directCalls(function)) {
                    calls.add(address(callee));
                }
                List<String> indirect = new ArrayList<>();
                List<Object> literals = new ArrayList<>();
                List<Object> mmio = new ArrayList<>();
                List<Object> backwards = new ArrayList<>();
                InstructionIterator instructions = currentProgram.getListing()
                    .getInstructions(function.getBody(), true);
                while (instructions.hasNext()) {
                    Instruction instruction = instructions.next();
                    long from = instruction.getAddress().getOffset();
                    if (instruction.getFlowType().isComputed()) {
                        indirect.add(address(from));
                    }
                    for (Reference reference : instruction.getReferencesFrom()) {
                        Address target = reference.getToAddress();
                        if (!reference.getReferenceType().isFlow()) {
                            literals.add(row(
                                "from", address(from),
                                "to", address(target.getOffset()),
                                "type", reference.getReferenceType().toString()));
                            if (isMmio(target)) {
                                Map<String, Object> mmioRow = row(
                                    "from", address(from),
                                    "address", address(target.getOffset()),
                                    "type", reference.getReferenceType().toString());
                                mmio.add(mmioRow);
                                unknownMmioWidths.add(mmioRow);
                                unknownMmioValues.add(mmioRow);
                            }
                        }
                        if (reference.getReferenceType().isFlow() &&
                            target.getOffset() <= from) {
                            Map<String, Object> branch = row(
                                "from", address(from),
                                "to", address(target.getOffset()),
                                "type", reference.getReferenceType().toString());
                            backwards.add(branch);
                            unboundedPolls.add(row(
                                "function", address(entry),
                                "from", address(from),
                                "to", address(target.getOffset())));
                        }
                    }
                }

                DecompileResults decompiled = decompiler.decompileFunction(function, 60, monitor);
                if (decompiled.decompileCompleted()) {
                    privateText.append("\n===== ")
                        .append(address(entry)).append(" =====\n")
                        .append(decompiled.getDecompiledFunction().getC());
                    java.util.Iterator<PcodeOpAST> operations =
                        decompiled.getHighFunction().getPcodeOps();
                    while (operations.hasNext()) {
                        PcodeOpAST operation = operations.next();
                        if (operation.getOpcode() != PcodeOp.LOAD &&
                            operation.getOpcode() != PcodeOp.STORE) {
                            continue;
                        }
                        Varnode pointer = operation.getInput(1);
                        if (!pointer.isConstant() && !pointer.isAddress()) {
                            Map<String, Object> unresolved = row(
                                "function", address(entry),
                                "instruction", address(operation.getSeqnum()
                                    .getTarget().getOffset()),
                                "operation", operation.getMnemonic());
                            computedMmio.add(unresolved);
                            unknownMemoryRanges.add(unresolved);
                        }
                    }
                } else {
                    unresolvedFunctions++;
                }

                functions.add(row(
                    "entry", address(entry),
                    "end_inclusive", address(function.getBody().getMaxAddress().getOffset()),
                    "sha256", HexFormat.of().formatHex(functionBytes(function)),
                    "depth", closureItem.getValue(),
                    "direct_calls", calls,
                    "indirect_control_flow", indirect,
                    "literal_references", literals,
                    "mmio_references", mmio,
                    "backward_branches", backwards));
            }
        } finally {
            decompiler.dispose();
        }

        functions.sort(Comparator.comparing(item ->
            (String) ((Map<?, ?>) item).get("entry")));
        boolean cancelled = monitor.isCancelled();
        boolean complete = !cancelled && unresolvedSeeds == 0 && unresolvedFunctions == 0;
        Memory memory = currentProgram.getMemory();
        Map<String, Object> report = row(
            "schema", "flyos.fr245.k28-reset-inventory.v1",
            "program", row(
                "name", currentProgram.getName(),
                "sha256", executableSha.toLowerCase(),
                "mapped_sha256", digest(mappedApplicationBytes()),
                "base", address(APP_BASE),
                "end_exclusive", address(APP_END_EXCLUSIVE)),
            "roots", List.of(address(RESET_HANDLER), address(stage2)),
            "max_depth", maxDepth,
            "analysis_complete", complete,
            "cancelled", cancelled,
            "unresolved_seed_count", unresolvedSeeds,
            "unresolved_function_count", unresolvedFunctions,
            "functions", functions,
            "computed_mmio", computedMmio,
            "unknown_mmio_widths", unknownMmioWidths,
            "unknown_mmio_values", unknownMmioValues,
            "unbounded_polls", unboundedPolls,
            "unknown_memory_ranges", unknownMemoryRanges);

        String json = new GsonBuilder().setPrettyPrinting().serializeNulls()
            .create().toJson(report) + "\n";
        checkOutputs(jsonPath, textPath);
        Files.createDirectories(jsonPath.getParent());
        Files.createDirectories(textPath.getParent());
        try (OutputStream jsonOut = Files.newOutputStream(
                 jsonPath, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
             OutputStream textOut = Files.newOutputStream(
                 textPath, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
            jsonOut.write(json.getBytes(StandardCharsets.UTF_8));
            textOut.write(privateText.toString().getBytes(StandardCharsets.UTF_8));
        }
        println("K28_RESET_CONTRACT_REPORT_COMPLETE inventory_sha256=" +
            digest(json.getBytes(StandardCharsets.UTF_8)) +
            " functions=" + functions.size() +
            " analysis_complete=" + complete);
    }
}
