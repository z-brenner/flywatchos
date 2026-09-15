#ifndef FLYOS_DRIVERS_HARDWARE_STUB_H
#define FLYOS_DRIVERS_HARDWARE_STUB_H

#define FLYOS_HW_UNIMPLEMENTED (-1)

int flyos_hw_display_init(void);
int flyos_hw_buttons_init(void);
int flyos_hw_power_init(void);
int flyos_hw_storage_init(void);

#endif
