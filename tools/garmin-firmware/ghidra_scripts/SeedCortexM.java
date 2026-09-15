// Seed a raw Cortex-M image from its vector table before auto-analysis.
//@category Garmin

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;
import ghidra.program.model.mem.Memory;

import java.math.BigInteger;

public class SeedCortexM extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        long vectorBase = args.length > 0 ? Long.decode(args[0]) : 0x3000L;
        int vectorCount = args.length > 1 ? Integer.decode(args[1]) : 128;

        Memory memory = currentProgram.getMemory();
        Register tMode = currentProgram.getProgramContext().getRegister("TMode");
        if (tMode == null) {
            throw new IllegalStateException("Selected language has no TMode register");
        }
        RegisterValue thumb = new RegisterValue(tMode, BigInteger.ONE);
        Address table = toAddr(vectorBase);
        int seeded = 0;

        for (int index = 1; index < vectorCount; index++) {
            Address slot = table.add(index * 4L);
            long raw = Integer.toUnsignedLong(memory.getInt(slot));
            if ((raw & 1L) == 0L) {
                continue;
            }
            Address target = toAddr(raw & ~1L);
            if (!memory.contains(target)) {
                continue;
            }

            boolean disassembled = getInstructionAt(target) != null;
            if (getInstructionContaining(target) == null) {
                currentProgram.getProgramContext().setRegisterValue(target, target, thumb);
                DisassembleCommand command =
                    new DisassembleCommand(new AddressSet(target, target), null, true);
                command.setInitialContext(thumb);
                disassembled = command.applyTo(currentProgram, monitor);
            }
            if (disassembled) {
                if (getFunctionAt(target) == null) {
                    createFunction(target, index == 1 ? "reset_handler" : null);
                }
                if (index == 1) {
                    createLabel(target, "reset_handler", true);
                    addEntryPoint(target);
                }
                seeded++;
            }
        }

        println("SeedCortexM: seeded " + seeded + " vector targets from " + table);
    }
}
