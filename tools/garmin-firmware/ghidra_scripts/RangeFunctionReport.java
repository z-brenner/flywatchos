// Lists functions and direct call edges within an address range.
// Usage: -postScript RangeFunctionReport.java <start> <end-inclusive>
//@category Garmin

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Set;

public class RangeFunctionReport extends GhidraScript {
    private String describe(Function function) {
        return function.getEntryPoint() + ".." + function.getBody().getMaxAddress() +
            " " + function.getName();
    }

    private List<Function> sorted(Set<Function> functions) {
        List<Function> result = new ArrayList<>(functions);
        result.sort(Comparator.comparing(Function::getEntryPoint));
        return result;
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2) throw new IllegalArgumentException("usage: <start> <end-inclusive>");
        Address start = toAddr(args[0]);
        Address end = toAddr(args[1]);
        AddressSet range = new AddressSet(start, end);
        FunctionIterator iterator = currentProgram.getFunctionManager().getFunctions(range, true);
        while (iterator.hasNext()) {
            Function function = iterator.next();
            println("function " + describe(function));
            for (Function caller : sorted(function.getCallingFunctions(monitor))) {
                println("  caller " + describe(caller));
            }
            for (Function callee : sorted(function.getCalledFunctions(monitor))) {
                println("  callee " + describe(callee));
            }
        }
    }
}
