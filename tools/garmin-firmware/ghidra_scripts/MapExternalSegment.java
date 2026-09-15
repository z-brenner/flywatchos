// Map the second executable region embedded after K28F internal flash.
//@category Garmin

import ghidra.app.script.GhidraScript;
import ghidra.app.util.MemoryBlockUtils;
import ghidra.app.util.importer.MessageLog;

import java.io.File;
import java.io.FileInputStream;

public class MapExternalSegment extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 3) {
            throw new IllegalArgumentException(
                "expected full image path, file offset, and runtime base");
        }
        File image = new File(args[0]);
        long fileOffset = Long.decode(args[1]);
        long runtimeBase = Long.decode(args[2]);
        long length = image.length() - fileOffset;
        if (!image.isFile() || fileOffset < 0 || length <= 0) {
            throw new IllegalArgumentException("invalid external-segment input");
        }
        if (currentProgram.getMemory().getBlock("external_xip") != null) {
            println("MapExternalSegment: external_xip already exists");
            return;
        }

        MessageLog log = new MessageLog();
        try (FileInputStream input = new FileInputStream(image)) {
            input.getChannel().position(fileOffset);
            MemoryBlockUtils.createInitializedBlock(
                currentProgram, false, "external_xip", toAddr(runtimeBase), input,
                length, "Second region from fw_all stream", image.getName(),
                true, false, true, log, monitor);
        }
        if (log.hasMessages()) println(log.toString());
        println("MapExternalSegment: mapped " + length + " bytes at " +
            toAddr(runtimeBase) + " from file offset 0x" + Long.toHexString(fileOffset));
    }
}
