#include "input/mock_input.h"
#include "fly/network.h"

uint8_t fly_button_from_key(int key) {
    switch (key) {
        case 'w': case 'W': return FLY_INPUT_UP;
        case 's': case 'S': return FLY_INPUT_DOWN;
        case 'a': case 'A': return FLY_INPUT_BACK;
        case 'd': case 'D': return FLY_INPUT_SELECT;
        case 'q': case 'Q': return FLY_INPUT_LIGHT;
        default: return 0u;
    }
}
