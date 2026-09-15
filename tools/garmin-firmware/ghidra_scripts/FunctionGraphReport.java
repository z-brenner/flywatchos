// Prints a bounded caller/callee graph for supplied function addresses.
// Usage: -postScript FunctionGraphReport.java <depth> <address>...
//@category Garmin

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class FunctionGraphReport extends GhidraScript {
    private static class Node {
        Function function;
        int depth;
        Node(Function function, int depth) { this.function = function; this.depth = depth; }
    }

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
        if (args.length < 2) {
            throw new IllegalArgumentException("usage: <depth> <address>...");
        }
        int maxDepth = Integer.decode(args[0]);
        FunctionManager manager = currentProgram.getFunctionManager();
        ArrayDeque<Node> queue = new ArrayDeque<>();
        Map<Address, Integer> bestDepth = new HashMap<>();

        for (int index = 1; index < args.length; index++) {
            Address address = toAddr(args[index]);
            Function function = manager.getFunctionAt(address);
            if (function == null) function = manager.getFunctionContaining(address);
            if (function == null) {
                println("unresolved_seed=" + address);
                continue;
            }
            queue.add(new Node(function, 0));
        }

        while (!queue.isEmpty()) {
            Node node = queue.removeFirst();
            Address entry = node.function.getEntryPoint();
            Integer previous = bestDepth.get(entry);
            if (previous != null && previous <= node.depth) continue;
            bestDepth.put(entry, node.depth);

            List<Function> callers = sorted(node.function.getCallingFunctions(monitor));
            List<Function> callees = sorted(node.function.getCalledFunctions(monitor));
            println("node depth=" + node.depth + " " + describe(node.function));
            for (Function caller : callers) println("  caller " + describe(caller));
            for (Function callee : callees) println("  callee " + describe(callee));

            if (node.depth >= maxDepth) continue;
            Set<Function> neighbors = new HashSet<>();
            neighbors.addAll(callers);
            neighbors.addAll(callees);
            for (Function neighbor : sorted(neighbors)) {
                queue.addLast(new Node(neighbor, node.depth + 1));
            }
        }
    }
}
