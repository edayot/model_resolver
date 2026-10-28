import java.io.PrintWriter;
import net.minecraft.SharedConstants;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.Bootstrap;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.Property;
import net.minecraft.world.level.material.FluidState;
import net.minecraft.world.phys.AABB;

/**
 * Prints one JSON object per block state: what fluids and occlusion need and no data file holds.
 * Run by scripts/generate_block_table.py with the server jar and its libraries.
 */
public class DumpBlocks {
    public static void main(String[] args) throws Exception {
        SharedConstants.tryDetectVersion();
        Bootstrap.bootStrap();
        try (PrintWriter out = new PrintWriter(args[0], "UTF-8")) {
            for (Block block : BuiltInRegistries.BLOCK) {
                String id = BuiltInRegistries.BLOCK.getKey(block).toString();
                for (BlockState state : block.getStateDefinition().getPossibleStates()) {
                    StringBuilder line = new StringBuilder();
                    line.append("{\"block\":\"").append(id).append("\",\"properties\":{");
                    boolean first = true;
                    for (Property.Value<?> value : (Iterable<Property.Value<?>>) state.getValues()::iterator) {
                        if (!first) line.append(',');
                        first = false;
                        line.append('"').append(value.property().getName()).append("\":\"").append(value.valueName()).append('"');
                    }
                    line.append("},\"solid\":").append(state.isSolid());
                    FluidState fluid = state.getFluidState();
                    if (fluid.isEmpty()) {
                        line.append(",\"fluid\":null");
                    } else {
                        line.append(",\"fluid\":[\"").append(BuiltInRegistries.FLUID.getKey(fluid.getType()))
                            .append("\",").append(fluid.getAmount()).append(',').append(!fluid.isSource() && fluid.getAmount() == 8).append(']');
                    }
                    line.append(",\"occlusion\":[");
                    first = true;
                    if (state.canOcclude()) {
                        for (AABB box : state.getOcclusionShape().toAabbs()) {
                            if (!first) line.append(',');
                            first = false;
                            line.append('[').append(box.minX).append(',').append(box.minY).append(',').append(box.minZ).append(',')
                                .append(box.maxX).append(',').append(box.maxY).append(',').append(box.maxZ).append(']');
                        }
                    }
                    line.append("]}");
                    out.println(line);
                }
            }
        }
    }
}
