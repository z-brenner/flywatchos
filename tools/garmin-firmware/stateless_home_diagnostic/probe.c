#include <stdint.h>

#define VIEW_ROOT_ADDR 0x20003e84u
#define HOME_ID 0x0005adf5u
#define NODE_LOW 0x1ffc0000u
#define NODE_HIGH 0x2003ffacu
#define USB_STATE (*(volatile const uint8_t *)0x1ffc6f25u)
#define UI_TASK (*(volatile const uint32_t *)0x1ffc7e14u)
#define DISPLAY_MUTEX ((volatile const uint8_t *)0x1ffde6ccu)
#define VIEW_MUTEX ((volatile const uint8_t *)0x200021d8u)
#define SOURCE_MUTEX ((volatile const uint8_t *)0x1ffc8dacu)
#define W 240u
#define H 240u

typedef uint32_t (*u32_fn)(void);
typedef uint32_t (*flush_fn)(uint8_t *, uint32_t);

enum view_class { VIEW_INVALID = 0u, VIEW_HOME = 1u, VIEW_NON_HOME = 2u };

typedef struct {
    uint32_t node;
    uint32_t prev;
    uint32_t next;
    uint32_t identity;
    uint32_t flags;
} node_sample;

typedef struct {
    node_sample nodes[8];
    uint32_t root;
    uint32_t visible_identity;
    uint8_t count;
} view_sample;

typedef struct {
    uint8_t kind;
    uint8_t identity_hash;
} classification;

static uint32_t current_task(void) { return ((u32_fn)0x00005c35u)(); }

static uint8_t valid_node(uint32_t node) {
    return (uint8_t)((node & 3u) == 0u && node >= NODE_LOW && node <= NODE_HIGH);
}

static uint8_t capture(view_sample *out) {
    uint32_t root = *(volatile const uint32_t *)VIEW_ROOT_ADDR;
    uint32_t node = root;
    uint32_t previous = 0u;
    uint32_t visible = 0u;
    unsigned count = 0u;
    if (root == 0u) return 0u;
    while (node != 0u) {
        if (count == 8u || valid_node(node) == 0u) return 0u;
        for (unsigned i = 0u; i < count; ++i)
            if (out->nodes[i].node == node) return 0u;
        node_sample *s = &out->nodes[count];
        s->node = node;
        s->prev = *(volatile const uint32_t *)(node + 0u);
        s->next = *(volatile const uint32_t *)(node + 4u);
        s->identity = *(volatile const uint32_t *)(node + 8u);
        s->flags = *(volatile const uint32_t *)(node + 0x50u);
        if (s->prev != previous) return 0u;
        if (s->next != 0u && valid_node(s->next) == 0u) return 0u;
        if (visible == 0u && (s->flags & 2u) == 0u) visible = s->identity;
        previous = node;
        node = s->next;
        ++count;
    }
    if (visible == 0u || *(volatile const uint32_t *)VIEW_ROOT_ADDR != root) return 0u;
    out->root = root;
    out->visible_identity = visible;
    out->count = (uint8_t)count;
    return 1u;
}

static uint8_t matches_live(const view_sample *saved) {
    uint32_t node = *(volatile const uint32_t *)VIEW_ROOT_ADDR;
    uint32_t previous = 0u;
    uint32_t visible = 0u;
    if (node != saved->root) return 0u;
    for (unsigned i = 0u; i < saved->count; ++i) {
        if (node == 0u || valid_node(node) == 0u || node != saved->nodes[i].node) return 0u;
        uint32_t prev = *(volatile const uint32_t *)(node + 0u);
        uint32_t next = *(volatile const uint32_t *)(node + 4u);
        uint32_t identity = *(volatile const uint32_t *)(node + 8u);
        uint32_t flags = *(volatile const uint32_t *)(node + 0x50u);
        if (prev != previous || prev != saved->nodes[i].prev ||
            next != saved->nodes[i].next || identity != saved->nodes[i].identity ||
            flags != saved->nodes[i].flags) return 0u;
        if (visible == 0u && (flags & 2u) == 0u) visible = identity;
        previous = node;
        node = next;
    }
    return (uint8_t)(node == 0u && visible == saved->visible_identity &&
                     *(volatile const uint32_t *)VIEW_ROOT_ADDR == saved->root);
}

static classification classify_view(void) {
    view_sample sample;
    classification result = { VIEW_INVALID, 0u };
    if (capture(&sample) == 0u || matches_live(&sample) == 0u) return result;
    uint32_t x = sample.visible_identity;
    x ^= x >> 16;
    x ^= x >> 8;
    result.identity_hash = (uint8_t)x;
    result.kind = sample.visible_identity == HOME_ID ? VIEW_HOME : VIEW_NON_HOME;
    return result;
}

static uint32_t rtc_sample(void) {
    volatile const uint32_t *rtc = (volatile const uint32_t *)0x4003d000u;
    for (unsigned attempt = 0u; attempt < 2u; ++attempt) {
        uint32_t before = rtc[0];
        uint32_t prescaler = rtc[1];
        uint32_t after = rtc[0];
        if (before == after) return (after << 15) | (prescaler & 0x7fffu);
    }
    return 0xffffffffu;
}

static uint8_t owner_state(volatile const uint8_t *mutex, uint32_t task) {
    uint32_t owner = *(volatile const uint32_t *)(mutex + 8u);
    if (owner == 0u) return 0u;
    return (uint8_t)(task != 0u && owner == task ? 1u : 2u);
}

static uint8_t mutex_code(volatile const uint8_t *mutex, uint32_t task) {
    uint8_t state = owner_state(mutex, task);
    uint16_t recursion = *(volatile const uint16_t *)(mutex + 24u);
    return (uint8_t)(state | (recursion != 0u ? 4u : 0u));
}

static void pixel(uint8_t *fb, unsigned x, unsigned y, uint8_t color) {
    if (x < W && y < H) fb[y * W + x] = color;
}

static uint16_t glyph(unsigned c) {
    static const uint16_t hex[16] = {
        0x7b6fu,0x74b2u,0x788eu,0x628eu,0x13edu,0x63a7u,0x7be3u,0x248fu,
        0x7befu,0x63efu,0x5beau,0x6baeu,0x3923u,0x6b6eu,0x79a7u,0x49a7u
    };
    if (c >= '0' && c <= '9') return hex[c - '0'];
    if (c >= 'A' && c <= 'F') return hex[c - 'A' + 10u];
    if (c == 'U') return 0x7b6du;
    if (c == 'C') return 0x3923u;
    if (c == 'T') return 0x2497u;
    if (c == 'Q') return 0x736fu;
    if (c == 'D') return 0x6b6eu;
    if (c == 'V') return 0x2b6du;
    if (c == 'S') return 0x63a7u;
    if (c == 'H') return 0x5bedu;
    if (c == 'N') return 0x5b6du;
    if (c == 'I') return 0x7492u;
    return 0u;
}

static void chr(uint8_t *fb, unsigned x, unsigned y, unsigned c, uint8_t color) {
    uint16_t bits = glyph(c);
    for (unsigned row = 0u; row < 5u; ++row)
        for (unsigned col = 0u; col < 3u; ++col)
            if ((bits & (1u << (row * 3u + col))) != 0u)
                pixel(fb, x + 2u - col, y + row, color);
}

static void hex8(uint8_t *fb, unsigned x, unsigned y, uint8_t value, uint8_t color) {
    chr(fb, x, y, (value >> 4) < 10u ? (unsigned)'0' + (value >> 4) : (unsigned)'A' + (value >> 4) - 10u, color);
    value &= 15u;
    chr(fb, x + 4u, y, value < 10u ? (unsigned)'0' + value : (unsigned)'A' + value - 10u, color);
}

static void hex32(uint8_t *fb, unsigned x, unsigned y, uint32_t value, uint8_t color) {
    for (unsigned shift = 32u; shift != 0u; shift -= 4u) {
        unsigned n = (value >> (shift - 4u)) & 15u;
        chr(fb, x, y, n < 10u ? '0' + n : 'A' + n - 10u, color);
        x += 4u;
    }
}

static void draw_panel(uint8_t *fb) {
    classification view = classify_view();
    if (view.kind != VIEW_HOME) return;
    uint32_t tick = rtc_sample();
    uint32_t task = current_task();
    uint8_t d = mutex_code(DISPLAY_MUTEX, task);
    uint8_t v = mutex_code(VIEW_MUTEX, task);
    uint8_t s = mutex_code(SOURCE_MUTEX, task);
    uint8_t usb = USB_STATE;
    uint8_t ui = (uint8_t)(task != 0u && task == UI_TASK);
    for (unsigned y = 8u; y < 43u; ++y)
        for (unsigned x = 16u; x < 68u; ++x) pixel(fb, x, y, 0u);
    chr(fb,16u,10u,'U',0x3fu); hex8(fb,20u,10u,usb <= 4u ? usb : 0xffu,0x3fu);
    chr(fb,16u,17u,'C',0x38u);
    chr(fb,20u,17u,view.kind == VIEW_HOME ? 'H' : view.kind == VIEW_NON_HOME ? 'N' : 'I',0x38u);
    hex8(fb,24u,17u,view.identity_hash,0x38u);
    chr(fb,16u,24u,'T',0x3fu); hex32(fb,20u,24u,tick,0x3fu);
    chr(fb,16u,31u,'Q',0x0cu); hex8(fb,20u,31u,ui,0x0cu);
    chr(fb,32u,31u,'D',0x0cu); hex8(fb,36u,31u,d,0x0cu);
    chr(fb,48u,31u,'V',0x0cu); hex8(fb,52u,31u,v,0x0cu);
    chr(fb,16u,38u,'S',0x0cu); hex8(fb,20u,38u,s,0x0cu);
}

__attribute__((section(".probe.entry"), used))
uint32_t probe_display(uint8_t *framebuffer, uint32_t ignored) {
    (void)ignored;
    if (framebuffer != (uint8_t *)0) draw_panel(framebuffer);
    return ((flush_fn)0x0000e1a5u)(framebuffer, 0u);
}
