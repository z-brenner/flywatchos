// Export references to exact addresses for reproducible call-graph tracing.
//@category Garmin

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

import java.io.File;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

public class ExportReferences extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            throw new IllegalArgumentException("expected output path and addresses");
        }
        File output = new File(args[0]);
        Files.createDirectories(output.toPath().getParent());
        try (PrintWriter out = new PrintWriter(output, StandardCharsets.UTF_8)) {
            out.printf("program: %s%n", currentProgram.getName());
            for (int i = 1; i < args.length; i++) {
                Address target = toAddr(Long.decode(args[i]) & ~1L);
                Function exact = getFunctionAt(target);
                Function containing = getFunctionContaining(target);
                out.printf("%ntarget: %s exact=%s containing=%s%n", target,
                    exact == null ? "none" : exact.getName(),
                    containing == null ? "none" : containing.getName() + "@" +
                        containing.getEntryPoint());
                ReferenceIterator references =
                    currentProgram.getReferenceManager().getReferencesTo(target);
                int count = 0;
                while (references.hasNext()) {
                    Reference reference = references.next();
                    Function source = getFunctionContaining(reference.getFromAddress());
                    out.printf("  from=%s type=%s function=%s%n",
                        reference.getFromAddress(), reference.getReferenceType(),
                        source == null ? "none" : source.getName() + "@" +
                            source.getEntryPoint());
                    count++;
                }
                out.printf("  reference_count=%d%n", count);
            }
        }
        println("Wrote " + output.getAbsolutePath());
    }
}
