// Decompile exact function entry addresses to a UTF-8 text report.
//@category Garmin

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

import java.io.File;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

public class DecompileFunctions extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            throw new IllegalArgumentException("expected output path and one or more addresses");
        }
        File output = new File(args[0]);
        Files.createDirectories(output.toPath().getParent());
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        try (PrintWriter out = new PrintWriter(output, StandardCharsets.UTF_8)) {
            out.printf("program: %s%n", currentProgram.getName());
            out.printf("mapped_min: %s%n", currentProgram.getMemory().getMinAddress());
            out.printf("mapped_max: %s%n", currentProgram.getMemory().getMaxAddress());
            for (int i = 1; i < args.length; i++) {
                Address address = toAddr(Long.decode(args[i]));
                Function function = getFunctionAt(address);
                if (function == null) function = getFunctionContaining(address);
                out.printf("%n===== requested=%s function=%s =====%n", address,
                    function == null ? "none" : function.getName() + "@" + function.getEntryPoint());
                if (function == null) continue;
                DecompileResults result = decompiler.decompileFunction(function, 120, monitor);
                if (!result.decompileCompleted()) {
                    out.println("decompile_error: " + result.getErrorMessage());
                    continue;
                }
                out.println(result.getDecompiledFunction().getC());
            }
        } finally {
            decompiler.dispose();
        }
        println("Wrote " + output.getAbsolutePath());
    }
}
