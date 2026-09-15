#include <stddef.h>
#include <stdint.h>

extern uint32_t _sidata;
extern uint32_t _sdata;
extern uint32_t _edata;
extern uint32_t _sbss;
extern uint32_t _ebss;
extern uint32_t _stack_top;

void flyos_target_main(void);
void Reset_Handler(void);
static void Default_Handler(void);

__attribute__((section(".isr_vector"), used))
const uintptr_t flyos_vectors[124] = {
    [0] = (uintptr_t)&_stack_top,
    [1] = (uintptr_t)Reset_Handler,
    [2] = (uintptr_t)Default_Handler,
    [3] = (uintptr_t)Default_Handler,
    [4] = (uintptr_t)Default_Handler,
    [5] = (uintptr_t)Default_Handler,
    [6] = (uintptr_t)Default_Handler,
    [11] = (uintptr_t)Default_Handler,
    [12] = (uintptr_t)Default_Handler,
    [14] = (uintptr_t)Default_Handler,
    [15] = (uintptr_t)Default_Handler,
};

__attribute__((section(".text.Reset_Handler"), used, noreturn))
void Reset_Handler(void) {
    uint32_t *source = &_sidata;
    for (uint32_t *destination = &_sdata; destination < &_edata;) {
        *destination++ = *source++;
    }
    for (uint32_t *destination = &_sbss; destination < &_ebss;) {
        *destination++ = 0u;
    }
    flyos_target_main();
    for (;;) {
        __asm volatile("wfi");
    }
}

static void Default_Handler(void) {
    for (;;) {
        __asm volatile("wfi");
    }
}
