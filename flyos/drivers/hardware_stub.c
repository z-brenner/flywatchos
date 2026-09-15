#include "drivers/hardware_stub.h"

/* These fail explicitly until register addresses, buses, and pin maps are recovered. */
int flyos_hw_display_init(void) { return FLYOS_HW_UNIMPLEMENTED; }
int flyos_hw_buttons_init(void) { return FLYOS_HW_UNIMPLEMENTED; }
int flyos_hw_power_init(void) { return FLYOS_HW_UNIMPLEMENTED; }
int flyos_hw_storage_init(void) { return FLYOS_HW_UNIMPLEMENTED; }
