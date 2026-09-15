// Reports Ghidra's function ownership and references for evidence-selected
// Forerunner 245 3.10 driver addresses. Run only after importing the non-Music
// 3.10 fw_all.bin at 0x3000; pass the required script argument "3.10".
// @category Garmin

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;

public class DriverLeadReport extends GhidraScript {
    private static final String[] ADDRESSES = {
        "0x000b5532", // battery telemetry-format string load
        "0x000b8c64", // key ISR work-item setup
        "0x000b8c92", // load of key ISR work-item name
        "0x000b8f24", // key deferred work-item setup
        "0x000b9d0c", // PMIC work-item setup
        "0x000c41ca", // first RTC-base literal load in observed cluster
        "0x000c43a4", "0x000c43c6", "0x000c43f0", "0x000c443a",
        "0x000c4478", "0x000c448a", "0x000c4506", "0x000c4886",
        "0x000c49ce", "0x000c4a14", "0x000c4a28", "0x000c4a56",
        "0x000c4ade", "0x000c4b58", "0x000c4b92", "0x000c4bd6",
        "0x000c4c94",
        "0x000c4e3e", // last RTC-base literal load in observed cluster
        "0x000c863c", // first USBHS-base literal load in observed cluster
        "0x000c8724", "0x000c8856", "0x000c8886", "0x000c88c6",
        "0x000c8920", "0x000c8a7a", "0x000c8c42", "0x000c8cb0",
        "0x000c8d28", "0x000c8d56", "0x000c8d8e", "0x000c8dc8",
        "0x000c8e56", "0x000c8fe2", "0x000c92a8", "0x000c9316",
        "0x000c93b2", "0x000c95d2", "0x000c97c6", "0x000c9808",
        "0x000c983e", "0x000ca4b6",
        "0x000ca53c", // last USBHS/PHY-base literal load in observed cluster
        "0x000cff88", // usb-manager source-path string
        "0x000d1784", // HWM_TFS string
        "0x0017bae8"  // pointer to backlight work-item name
    };

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1 || !"3.10".equals(args[0])) {
            throw new IllegalArgumentException("DriverLeadReport requires argument: 3.10");
        }
        println("program=" + currentProgram.getName());
        println("image_base=" + currentProgram.getImageBase());
        for (String value : ADDRESSES) {
            Address address = toAddr(value);
            Function function = getFunctionContaining(address);
            Instruction instruction = getInstructionAt(address);
            String functionText = function == null ? "none" :
                function.getEntryPoint() + ".." + function.getBody().getMaxAddress() +
                " " + function.getName();
            String instructionText = instruction == null ? "none" : instruction.toString();
            println(value + " function=" + functionText + " instruction=" + instructionText);
            for (Reference reference : getReferencesTo(address)) {
                println("  ref_from=" + reference.getFromAddress() + " type=" + reference.getReferenceType());
            }
        }
    }
}
