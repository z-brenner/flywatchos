// Report references and function ownership for exact addresses supplied on the command line.
//@category Garmin

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;

public class AddressXrefReport extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length == 0) {
            throw new IllegalArgumentException("expected one or more addresses");
        }
        println("program=" + currentProgram.getName());
        for (String value : args) {
            Address address = toAddr(Long.decode(value));
            Function owner = getFunctionContaining(address);
            Instruction instruction = getInstructionAt(address);
            println("address=" + address + " owner=" + describe(owner) +
                " instruction=" + (instruction == null ? "none" : instruction));
            for (Reference reference : getReferencesTo(address)) {
                Function from = getFunctionContaining(reference.getFromAddress());
                println("  from=" + reference.getFromAddress() + " type=" +
                    reference.getReferenceType() + " owner=" + describe(from));
            }
        }
    }

    private String describe(Function function) {
        if (function == null) return "none";
        return function.getName() + "@" + function.getEntryPoint() + ".." +
            function.getBody().getMaxAddress();
    }
}
