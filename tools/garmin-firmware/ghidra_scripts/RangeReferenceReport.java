// Report every Ghidra reference whose destination lies in an inclusive range.
// Usage: -postScript RangeReferenceReport.java <output> <start> <end-inclusive>
//@category Garmin

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressIterator;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

import java.io.File;
import java.io.PrintWriter;

public class RangeReferenceReport extends GhidraScript {
    private String owner(Address address) {
        Function function = getFunctionContaining(address);
        if (function == null) return "none";
        return function.getName() + "@" + function.getEntryPoint() + ".." +
            function.getBody().getMaxAddress();
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 3) {
            throw new IllegalArgumentException(
                "usage: <output> <start> <end-inclusive>");
        }
        Address start = toAddr(args[1]);
        Address end = toAddr(args[2]);
        AddressSet range = new AddressSet(start, end);
        long count = 0;
        try (PrintWriter out = new PrintWriter(new File(args[0]))) {
            out.println("program=" + currentProgram.getName());
            out.println("range=" + start + ".." + end);
            AddressIterator destinations = currentProgram.getReferenceManager()
                .getReferenceDestinationIterator(range, true);
            while (destinations.hasNext()) {
                Address to = destinations.next();
                for (Reference ref : getReferencesTo(to)) {
                    count++;
                    out.println("to=" + to + " from=" + ref.getFromAddress() +
                        " type=" + ref.getReferenceType() +
                        " owner=" + owner(ref.getFromAddress()));
                }
            }
            out.println("reference_count=" + count);
        }
        println("wrote " + args[0] + " with " + count + " references");
    }
}
