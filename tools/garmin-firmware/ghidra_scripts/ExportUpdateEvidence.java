// Export concrete string, reference, and containing-function evidence from an
// already analyzed Forerunner 245 fw_all binary.  This script is read-only with
// respect to the input program; it writes a UTF-8 report to the path supplied
// as its only script argument.
//@category Garmin

import java.io.File;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Iterator;
import java.util.List;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSetView;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

public class ExportUpdateEvidence extends GhidraScript {
    private static final List<String> ANCHORS = Arrays.asList(
        "0:/Garmin/GUPDATE.GCD",
        "GUPDATE.GCD",
        "UpdateFile",
        "..\\..\\..\\HWM\\k28\\hwm_system_update.c",
        "..\\..\\..\\HWM\\core\\garminos\\service\\software-update\\hwm_update.c: 169",
        "Signature check failed on file:",
        "checksum read from the file is 0",
        "checksum calc"
    );

    // Addresses proved independently from literal-load decoding.  Entries
    // outside the current image are ignored, allowing the same script to run
    // against both preserved non-Music releases.
    private static final Object[][] CODE_SITES = {
        { "13.70", 0x00009b82L, "hwm_system_update.c assertion path" },
        { "3.10", 0x000a0184L, "loads 0:/Garmin/GUPDATE.GCD" },
        { "3.10", 0x000a0474L, "opens/tests 0:/Garmin/GUPDATE.GCD" }
    };

    private List<Address> findAll(byte[] needle) throws Exception {
        List<Address> hits = new ArrayList<>();
        Memory memory = currentProgram.getMemory();
        AddressSetView initialized = memory.getAllInitializedAddressSet();
        for (ghidra.program.model.address.AddressRange range : initialized) {
            Address cursor = range.getMinAddress();
            while (cursor != null && cursor.compareTo(range.getMaxAddress()) <= 0) {
                Address hit = memory.findBytes(cursor, range.getMaxAddress(), needle, null, true, monitor);
                if (hit == null) break;
                hits.add(hit);
                cursor = hit.add(1);
            }
        }
        return hits;
    }

    private void emitFunction(PrintWriter out, Function function) {
        if (function == null) {
            out.println("    containing_function: none");
            return;
        }
        out.printf("    containing_function: %s @ %s%n", function.getName(), function.getEntryPoint());
        Listing listing = currentProgram.getListing();
        Iterator<Instruction> instructions = listing.getInstructions(function.getBody(), true);
        int count = 0;
        while (instructions.hasNext() && count < 80) {
            Instruction instruction = instructions.next();
            out.printf("      %s  %s%n", instruction.getAddress(), instruction.toString());
            count++;
        }
        if (count == 80) out.println("      ... truncated after 80 instructions");
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 1 || args.length > 2) {
            throw new IllegalArgumentException("expected output path and optional image version");
        }
        String imageVersion = args.length == 2 ? args[1] : "unknown";
        File output = new File(args[0]);
        Files.createDirectories(output.toPath().getParent());
        try (PrintWriter out = new PrintWriter(output, StandardCharsets.UTF_8)) {
            out.printf("program: %s%n", currentProgram.getName());
            out.printf("language: %s%n", currentProgram.getLanguageID());
            out.printf("image_base: %s%n", currentProgram.getImageBase());
            out.printf("mapped_min: %s%n", currentProgram.getMemory().getMinAddress());
            out.printf("mapped_max: %s%n", currentProgram.getMemory().getMaxAddress());
            out.printf("image_version: %s%n", imageVersion);
            for (String anchor : ANCHORS) {
                byte[] needle = anchor.getBytes(StandardCharsets.US_ASCII);
                List<Address> hits = findAll(needle);
                out.printf("%nanchor: %s%n", anchor);
                out.printf("occurrences: %d%n", hits.size());
                for (Address hit : hits) {
                    out.printf("  address: %s%n", hit);
                    ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(hit);
                    int refCount = 0;
                    while (refs.hasNext()) {
                        Reference ref = refs.next();
                        Address from = ref.getFromAddress();
                        out.printf("  reference: %s type=%s%n", from, ref.getReferenceType());
                        emitFunction(out, currentProgram.getFunctionManager().getFunctionContaining(from));
                        refCount++;
                    }
                    if (refCount == 0) out.println("  references: none recognized by Ghidra");
                }
            }
            out.println("\nknown_code_sites:");
            for (Object[] descriptor : CODE_SITES) {
                String siteVersion = (String)descriptor[0];
                if (!imageVersion.equals("unknown") && !imageVersion.equals(siteVersion)) continue;
                long raw = (Long)descriptor[1];
                String note = (String)descriptor[2];
                Address site = toAddr(raw);
                if (!currentProgram.getMemory().contains(site)) continue;
                Instruction instruction = currentProgram.getListing().getInstructionAt(site);
                out.printf("  site: %s version=%s note=%s instruction=%s%n", site,
                    siteVersion, note,
                    instruction == null ? "not defined" : instruction.toString());
                emitFunction(out, currentProgram.getFunctionManager().getFunctionContaining(site));
            }
        }
        println("Wrote " + output.getAbsolutePath());
    }
}
