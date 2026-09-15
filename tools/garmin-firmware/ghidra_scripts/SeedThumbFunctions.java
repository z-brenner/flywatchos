// Seed exact Thumb function entry addresses supplied on the command line.
//@category Garmin

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;

import java.math.BigInteger;

public class SeedThumbFunctions extends GhidraScript {
    @Override
    public void run() throws Exception {
        Register tMode = currentProgram.getProgramContext().getRegister("TMode");
        RegisterValue thumb = new RegisterValue(tMode, BigInteger.ONE);
        for (String arg : getScriptArgs()) {
            Address address = toAddr(Long.decode(arg) & ~1L);
            currentProgram.getProgramContext().setRegisterValue(address, address, thumb);
            DisassembleCommand command = new DisassembleCommand(
                new AddressSet(address, address), null, true);
            command.setInitialContext(thumb);
            if (!command.applyTo(currentProgram, monitor)) {
                println("failed=" + address);
                continue;
            }
            if (getFunctionAt(address) == null) createFunction(address, null);
            println("seeded=" + address);
        }
    }
}
