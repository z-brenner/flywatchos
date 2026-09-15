#include "display/neural_specimen.h"

const FlyNeuralSpecimenPoint
    fly_neural_specimen_points[FLY_NEURAL_SPECIMEN_CELLS] = {
    { 88u, 83u, 7u, 7u }, { 96u, 83u, 7u, 7u },
    {104u, 83u, 7u, 7u }, {112u, 83u, 7u, 7u },
    {120u, 83u, 7u, 7u }, {128u, 83u, 7u, 7u },
    {136u, 83u, 7u, 7u }, {144u, 83u, 7u, 7u },
    { 88u, 91u, 7u, 7u }, { 96u, 91u, 7u, 7u },
    {104u, 91u, 7u, 7u }, {112u, 91u, 7u, 7u },
    {120u, 91u, 7u, 7u }, {128u, 91u, 7u, 7u },
    {136u, 91u, 7u, 7u }, {144u, 91u, 7u, 7u },
    { 88u, 99u, 7u, 7u }, { 96u, 99u, 7u, 7u },
    {104u, 99u, 7u, 7u }, {112u, 99u, 7u, 7u },
    {120u, 99u, 7u, 7u }, {128u, 99u, 7u, 7u },
    {136u, 99u, 7u, 7u }, {144u, 99u, 7u, 7u },
    { 88u,107u, 7u, 7u }, { 96u,107u, 7u, 7u },
    {104u,107u, 7u, 7u }, {112u,107u, 7u, 7u },
    {120u,107u, 7u, 7u }, {128u,107u, 7u, 7u },
    {136u,107u, 7u, 7u }, {144u,107u, 7u, 7u },
    { 88u,115u, 7u, 7u }, { 96u,115u, 7u, 7u },
    {104u,115u, 7u, 7u }, {112u,115u, 7u, 7u },
    {120u,115u, 7u, 7u }, {128u,115u, 7u, 7u },
    {136u,115u, 7u, 7u }, {144u,115u, 7u, 7u },
    { 88u,123u, 7u, 7u }, { 96u,123u, 7u, 7u },
    {104u,123u, 7u, 7u }, {112u,123u, 7u, 7u },
    {120u,123u, 7u, 7u }, {128u,123u, 7u, 7u },
    {136u,123u, 7u, 7u }, {144u,123u, 7u, 7u },
    { 88u,131u, 7u, 7u }, { 96u,131u, 7u, 7u },
    {104u,131u, 7u, 7u }, {112u,131u, 7u, 7u },
    {120u,131u, 7u, 7u }, {128u,131u, 7u, 7u },
    {136u,131u, 7u, 7u }, {144u,131u, 7u, 7u },
    { 88u,139u, 7u, 7u }, { 96u,139u, 7u, 7u },
    {104u,139u, 7u, 7u }, {112u,139u, 7u, 7u },
    {120u,139u, 7u, 7u }, {128u,139u, 7u, 7u },
    {136u,139u, 7u, 7u }, {144u,139u, 7u, 7u }
};

static const uint8_t *fly_neural_specimen_glyph(char c) {
    static const uint8_t blank[7] = {0u};
    static const uint8_t digits[10][7] = {
        {14u,17u,19u,21u,25u,17u,14u}, {4u,12u,4u,4u,4u,4u,14u},
        {14u,17u,1u,2u,4u,8u,31u}, {30u,1u,1u,14u,1u,1u,30u},
        {2u,6u,10u,18u,31u,2u,2u}, {31u,16u,16u,30u,1u,1u,30u},
        {14u,16u,16u,30u,17u,17u,14u}, {31u,1u,2u,4u,8u,8u,8u},
        {14u,17u,17u,14u,17u,17u,14u}, {14u,17u,17u,15u,1u,1u,14u}
    };
    static const uint8_t alpha[26][7] = {
        {14u,17u,17u,31u,17u,17u,17u}, {30u,17u,17u,30u,17u,17u,30u},
        {14u,17u,16u,16u,16u,17u,14u}, {30u,17u,17u,17u,17u,17u,30u},
        {31u,16u,16u,30u,16u,16u,31u}, {31u,16u,16u,30u,16u,16u,16u},
        {14u,17u,16u,23u,17u,17u,15u}, {17u,17u,17u,31u,17u,17u,17u},
        {14u,4u,4u,4u,4u,4u,14u}, {7u,2u,2u,2u,18u,18u,12u},
        {17u,18u,20u,24u,20u,18u,17u}, {16u,16u,16u,16u,16u,16u,31u},
        {17u,27u,21u,21u,17u,17u,17u}, {17u,25u,21u,19u,17u,17u,17u},
        {14u,17u,17u,17u,17u,17u,14u}, {30u,17u,17u,30u,16u,16u,16u},
        {14u,17u,17u,17u,21u,18u,13u}, {30u,17u,17u,30u,20u,18u,17u},
        {15u,16u,16u,14u,1u,1u,30u}, {31u,4u,4u,4u,4u,4u,4u},
        {17u,17u,17u,17u,17u,17u,14u}, {17u,17u,17u,17u,17u,10u,4u},
        {17u,17u,17u,21u,21u,21u,10u}, {17u,17u,10u,4u,10u,17u,17u},
        {17u,17u,10u,4u,4u,4u,4u}, {31u,1u,2u,4u,8u,16u,31u}
    };
    static const uint8_t dash[7] = {0u,0u,0u,31u,0u,0u,0u};
    static const uint8_t slash[7] = {1u,2u,4u,8u,16u,0u,0u};
    static const uint8_t greater[7] = {16u,8u,4u,2u,4u,8u,16u};

    if (c >= '0' && c <= '9') return digits[c - '0'];
    if (c >= 'A' && c <= 'Z') return alpha[c - 'A'];
    if (c == '-') return dash;
    if (c == '/') return slash;
    if (c == '>') return greater;
    return blank;
}

static void fly_neural_specimen_pixel(uint8_t framebuffer[], int x, int y,
                                      uint8_t role) {
    if (x >= 0 && x < (int)FLY_NEURAL_SPECIMEN_WIDTH &&
        y >= 0 && y < (int)FLY_NEURAL_SPECIMEN_HEIGHT)
        framebuffer[(unsigned)y * FLY_NEURAL_SPECIMEN_WIDTH + (unsigned)x] = role;
}

static void fly_neural_specimen_line(uint8_t framebuffer[], int x0, int y0,
                                     int x1, int y1, uint8_t role) {
    int dx = x1 > x0 ? x1 - x0 : x0 - x1;
    int sx = x0 < x1 ? 1 : -1;
    int dy = y1 > y0 ? y0 - y1 : y1 - y0;
    int sy = y0 < y1 ? 1 : -1;
    int error = dx + dy;

    for (;;) {
        fly_neural_specimen_pixel(framebuffer, x0, y0, role);
        if (x0 == x1 && y0 == y1) return;
        {
            int twice = 2 * error;
            if (twice >= dy) { error += dy; x0 += sx; }
            if (twice <= dx) { error += dx; y0 += sy; }
        }
    }
}

static void fly_neural_specimen_text(uint8_t framebuffer[], int x, int y,
                                     const char *text, uint8_t role) {
    for (; *text != '\0'; ++text, x += 6) {
        const uint8_t *rows = fly_neural_specimen_glyph(*text);

        for (unsigned row = 0u; row < 7u; ++row)
            for (unsigned col = 0u; col < 5u; ++col)
                if ((rows[row] & (uint8_t)(1u << (4u - col))) != 0u)
                    fly_neural_specimen_pixel(framebuffer, x + (int)col,
                                              y + (int)row, role);
    }
}

static int fly_neural_specimen_unsigned(uint8_t framebuffer[], int x, int y,
                                        uint32_t value, uint8_t role) {
    char digits[10];
    unsigned count = 0u;

    do {
        digits[count++] = (char)('0' + value % 10u);
        value /= 10u;
    } while (value != 0u);
    while (count != 0u) {
        fly_neural_specimen_text(framebuffer, x, y, (char[]){digits[--count], '\0'}, role);
        x += 6;
    }
    return x;
}

static uint8_t fly_neural_specimen_level(const FlyBrain64 *brain, unsigned neuron) {
    int32_t value = brain->activation[neuron];
    uint32_t magnitude = (uint32_t)(value < 0 ? -value : value);

    if (magnitude < 128u) return 0u;
    if (magnitude < 256u) return 1u;
    if (magnitude < 512u) return 2u;
    return 3u;
}

static void fly_neural_specimen_cell(uint8_t framebuffer[],
                                     const FlyNeuralSpecimenPoint *point,
                                     uint8_t level, uint8_t role) {
    int x = (int)point->x + 1;
    int y = (int)point->y + 1;

    if (level == 0u) {
        fly_neural_specimen_pixel(framebuffer, x + 2, y + 2, role);
    } else if (level == 1u) {
        fly_neural_specimen_line(framebuffer, x + 2, y, x + 2, y + 4, role);
        fly_neural_specimen_line(framebuffer, x, y + 2, x + 4, y + 2, role);
    } else if (level == 2u) {
        fly_neural_specimen_line(framebuffer, x, y, x + 4, y, role);
        fly_neural_specimen_line(framebuffer, x + 4, y, x + 4, y + 4, role);
        fly_neural_specimen_line(framebuffer, x + 4, y + 4, x, y + 4, role);
        fly_neural_specimen_line(framebuffer, x, y + 4, x, y, role);
    } else {
        for (int row = 0; row < 5; ++row)
            for (int col = 0; col < 5; ++col)
                fly_neural_specimen_pixel(framebuffer, x + col, y + row, role);
    }
}

static const char *fly_neural_specimen_state(uint8_t state) {
    if (state == FLY_BRAIN64_STATE_MOVEMENT) return "MOVE";
    if (state == FLY_BRAIN64_STATE_AROUSAL) return "AROUSE";
    if (state == FLY_BRAIN64_STATE_QUIET) return "QUIET";
    return "REST";
}

const char *fly_neural_specimen_button_label(uint8_t buttons) {
    if ((buttons & FLY_BRAIN64_BUTTON_LIGHT) != 0u) return "LIGHT > LUX GATE";
    if ((buttons & FLY_BRAIN64_BUTTON_START) != 0u) return "START > MOTOR BURST";
    if ((buttons & FLY_BRAIN64_BUTTON_BACK) != 0u) return "BACK > GARMIN VIEW";
    if ((buttons & FLY_BRAIN64_BUTTON_DOWN) != 0u) return "DOWN > CALM FIELD";
    if ((buttons & FLY_BRAIN64_BUTTON_UP) != 0u) return "UP > PULSE SEEK";
    return "";
}
const char *fly_neural_specimen_unavailable_label(unsigned rail) {
    static const char *labels[] = {"HR --", "MOTION --", "B --"};
    return rail < 3u ? labels[rail] : "";
}

static const char *fly_neural_specimen_footer(const FlyBrainInputs *inputs) {
    const char *button_label = fly_neural_specimen_button_label(inputs->buttons);

    if (button_label[0] != '\0') return button_label;
    if ((inputs->valid_mask & FLY_BRAIN64_VALID_CHARGING) != 0u &&
        inputs->charging != 0u) return "CHARGING / N64";
    return "N64 / READY";
}

static void fly_neural_specimen_sensor_rail(uint8_t framebuffer[],
                                            const FlyBrain64 *brain,
                                            const FlyBrainInputs *inputs) {
    fly_neural_specimen_line(framebuffer, 54, 169, 186, 169,
                             FLY_NEURAL_SPECIMEN_SCAFFOLD);
    fly_neural_specimen_line(framebuffer, 54, 203, 186, 203,
                             FLY_NEURAL_SPECIMEN_SCAFFOLD);
    if ((inputs->valid_mask & FLY_BRAIN64_VALID_HEART_RATE) != 0u) {
        fly_neural_specimen_text(framebuffer, 58, 174, "HR ", FLY_NEURAL_SPECIMEN_TEXT);
        (void)fly_neural_specimen_unsigned(framebuffer, 76, 174,
                                            inputs->heart_rate_bpm,
                                            FLY_NEURAL_SPECIMEN_TEXT);
    } else {
        fly_neural_specimen_text(framebuffer, 58, 174, fly_neural_specimen_unavailable_label(0u),
                                 FLY_NEURAL_SPECIMEN_TEXT);
    }
    if ((inputs->valid_mask & FLY_BRAIN64_VALID_MOTION) != 0u) {
        int32_t motion = inputs->motion;
        int x = 100;
        fly_neural_specimen_text(framebuffer, 58, 184, "MOTION ", FLY_NEURAL_SPECIMEN_TEXT);
        if (motion < 0) {
            fly_neural_specimen_text(framebuffer, x, 184, "-", FLY_NEURAL_SPECIMEN_TEXT);
            x += 6;
            motion = -motion;
        }
        (void)fly_neural_specimen_unsigned(framebuffer, x, 184, (uint32_t)motion,
                                            FLY_NEURAL_SPECIMEN_TEXT);
    } else {
        fly_neural_specimen_text(framebuffer, 58, 184, fly_neural_specimen_unavailable_label(1u),
                                 FLY_NEURAL_SPECIMEN_TEXT);
    }
    if ((inputs->valid_mask & FLY_BRAIN64_VALID_BATTERY) != 0u) {
        fly_neural_specimen_text(framebuffer, 136, 174, "B ", FLY_NEURAL_SPECIMEN_TEXT);
        (void)fly_neural_specimen_unsigned(framebuffer, 148, 174,
                                            inputs->battery_percent,
                                            FLY_NEURAL_SPECIMEN_TEXT);
    } else {
        fly_neural_specimen_text(framebuffer, 136, 174, fly_neural_specimen_unavailable_label(2u),
                                 FLY_NEURAL_SPECIMEN_TEXT);
    }
    fly_neural_specimen_text(framebuffer, 136, 184, fly_neural_specimen_state(brain->state),
                             FLY_NEURAL_SPECIMEN_TEXT);
}
void fly_neural_specimen_render_if_home(
    uint8_t framebuffer[FLY_NEURAL_SPECIMEN_FRAMEBUFFER_BYTES], uint8_t home_gate,
                                        const FlyBrain64 *brain, const FlyBrainInputs *inputs,
                                        uint32_t rtc_tick) {
    if (home_gate != 0u) fly_neural_specimen_render(framebuffer, brain, inputs, rtc_tick);
}

void fly_neural_specimen_render(
    uint8_t framebuffer[FLY_NEURAL_SPECIMEN_FRAMEBUFFER_BYTES],
    const FlyBrain64 *brain, const FlyBrainInputs *inputs, uint32_t rtc_tick) {
    static const int contour[][2] = {
        {120,48}, {98,55}, {72,76}, {54,111}, {72,149}, {94,166},
        {120,166}, {146,166}, {168,149}, {186,111}, {168,76}, {142,55}, {120,48}
    };

    for (unsigned pixel = 0u; pixel < FLY_NEURAL_SPECIMEN_FRAMEBUFFER_BYTES; ++pixel)
        framebuffer[pixel] = FLY_NEURAL_SPECIMEN_BLACK;
    fly_neural_specimen_text(framebuffer, 105, 14, "PHASE", FLY_NEURAL_SPECIMEN_TEXT);
    fly_neural_specimen_text(framebuffer, 84, 28, "FLYOS // N64",
                             FLY_NEURAL_SPECIMEN_TEXT);
    fly_neural_specimen_pixel(framebuffer, 88 + (int)(rtc_tick & 0x3fu), 24,
                              FLY_NEURAL_SPECIMEN_TEXT);
    fly_neural_specimen_line(framebuffer, 98, 55, 76, 44,
                             FLY_NEURAL_SPECIMEN_SCAFFOLD);
    fly_neural_specimen_line(framebuffer, 76, 44, 66, 50,
                             FLY_NEURAL_SPECIMEN_SCAFFOLD);
    fly_neural_specimen_line(framebuffer, 142, 55, 164, 44,
                             FLY_NEURAL_SPECIMEN_SCAFFOLD);
    fly_neural_specimen_line(framebuffer, 164, 44, 174, 50,
                             FLY_NEURAL_SPECIMEN_SCAFFOLD);
    for (unsigned i = 0u; i + 1u < sizeof(contour) / sizeof(contour[0]); ++i)
        fly_neural_specimen_line(framebuffer, contour[i][0], contour[i][1],
                                 contour[i + 1u][0], contour[i + 1u][1],
                                 FLY_NEURAL_SPECIMEN_SCAFFOLD);
    fly_neural_specimen_line(framebuffer, 72, 76, 96, 91,
                             FLY_NEURAL_SPECIMEN_SCAFFOLD);
    fly_neural_specimen_line(framebuffer, 54, 111, 92, 116,
                             FLY_NEURAL_SPECIMEN_SCAFFOLD);
    fly_neural_specimen_line(framebuffer, 72, 149, 96, 131,
                             FLY_NEURAL_SPECIMEN_SCAFFOLD);
    fly_neural_specimen_line(framebuffer, 168, 76, 144, 91,
                             FLY_NEURAL_SPECIMEN_SCAFFOLD);
    fly_neural_specimen_line(framebuffer, 186, 111, 148, 116,
                             FLY_NEURAL_SPECIMEN_SCAFFOLD);
    fly_neural_specimen_line(framebuffer, 168, 149, 144, 131,
                             FLY_NEURAL_SPECIMEN_SCAFFOLD);
    fly_neural_specimen_text(framebuffer, 58, 58, "LUX", FLY_NEURAL_SPECIMEN_TEXT);
    fly_neural_specimen_text(framebuffer, 58, 116, "WAKE", FLY_NEURAL_SPECIMEN_TEXT);
    fly_neural_specimen_text(framebuffer, 58, 154, "CALM", FLY_NEURAL_SPECIMEN_TEXT);
    fly_neural_specimen_text(framebuffer, 150, 58, "PULSE", FLY_NEURAL_SPECIMEN_TEXT);
    fly_neural_specimen_text(framebuffer, 162, 154, "SYS", FLY_NEURAL_SPECIMEN_TEXT);
    for (unsigned neuron = 0u; neuron < FLY_NEURAL_SPECIMEN_CELLS; ++neuron) {
        uint8_t role = brain->activation[neuron] < 0 ?
                           FLY_NEURAL_SPECIMEN_INHIBITORY :
                       (neuron >= 56u && fly_neural_specimen_level(brain, neuron) == 3u) ?
                           FLY_NEURAL_SPECIMEN_SATURATED : FLY_NEURAL_SPECIMEN_EXCITATORY;
        fly_neural_specimen_cell(framebuffer, &fly_neural_specimen_points[neuron],
                                 fly_neural_specimen_level(brain, neuron), role);
    }
    fly_neural_specimen_sensor_rail(framebuffer, brain, inputs);
    fly_neural_specimen_text(framebuffer, 66, 210,
                             fly_neural_specimen_footer(inputs),
                             FLY_NEURAL_SPECIMEN_TEXT);
}
