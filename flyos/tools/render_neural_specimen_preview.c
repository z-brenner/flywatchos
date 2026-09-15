#include "display/neural_specimen.h"
#include <stdio.h>
#include <string.h>

typedef struct { const char *name; uint8_t button, valid_mask, battery, charging, state; uint16_t hr; int16_t motion; uint32_t pattern; } Scenario;
static const Scenario scenarios[] = {
 {"quiet",0,0,0,0,FLY_BRAIN64_STATE_QUIET,0,0,1}, {"light",1,0,0,0,FLY_BRAIN64_STATE_AROUSAL,0,0,2},
 {"start",2,0,0,0,FLY_BRAIN64_STATE_AROUSAL,0,0,3}, {"back",4,0,0,0,FLY_BRAIN64_STATE_AROUSAL,0,0,4},
 {"down",8,0,0,0,FLY_BRAIN64_STATE_AROUSAL,0,0,5}, {"up",16,0,0,0,FLY_BRAIN64_STATE_AROUSAL,0,0,6},
 {"sensors-valid",0,7,87,0,FLY_BRAIN64_STATE_MOVEMENT,72,240,7}, {"sensors-invalid",0,0,0,0,FLY_BRAIN64_STATE_REST,0,0,8},
 {"charging",0,12,87,1,FLY_BRAIN64_STATE_REST,0,0,9}
 ,{"usb-pass-through",0,0,0,0,FLY_BRAIN64_STATE_REST,0,0,10}
 ,{"update-pass-through",0,0,0,0,FLY_BRAIN64_STATE_REST,0,0,11}
};
static int write_one(const char *out, const Scenario *s) {
 static const uint8_t pal[6][3]={{8,10,9},{54,69,59},{218,231,211},{135,184,122},{184,122,135},{242,210,94}};
 char path[512]; uint8_t fb[FLY_NEURAL_SPECIMEN_FRAMEBUFFER_BYTES]; FlyBrain64 brain={0}; FlyBrainInputs in={0}; FILE *f;
 for(unsigned n=0;n<64;n++) brain.activation[n]=(n&1u)?-(int16_t)(128u*((n+s->pattern)%4u)):(int16_t)(128u*((n+s->pattern)%4u));
 if(strcmp(s->name,"quiet")!=0) for(unsigned n=56;n<64;n++) brain.activation[n]=512;
 brain.state=s->state;
 in.buttons=s->button; in.valid_mask=s->valid_mask; in.heart_rate_bpm=s->hr; in.motion=s->motion; in.battery_percent=s->battery; in.charging=s->charging;
 for(unsigned i=0;i<sizeof(fb);i++) fb[i]=(uint8_t)((i/240u+i%240u+s->pattern)%6u);
 if(strstr(s->name,"pass-through")!=NULL) fly_neural_specimen_render_if_home(fb,0u,&brain,&in,s->pattern);
 else fly_neural_specimen_render_if_home(fb,1u,&brain,&in,s->pattern);
 (void)snprintf(path,sizeof(path),"%s/%s.ppm",out,s->name); f=fopen(path,"wb"); if(!f)return -1;
 (void)fprintf(f,"P6\n240 240\n255\n"); for(unsigned i=0;i<sizeof(fb);i++) if(fwrite(pal[fb[i]],1,3,f)!=3){fclose(f);return -1;} return fclose(f);
}
int main(int argc,char **argv){if(argc!=3||strcmp(argv[1],"--output")!=0)return 2;for(unsigned i=0;i<sizeof(scenarios)/sizeof(scenarios[0]);i++)if(write_one(argv[2],&scenarios[i]))return 1;return 0;}
