
#include "materials8k.h"
namespace astra::materials8k {
KTXConfig config_for_tier(Tier t){
 switch(t){ case Tier::LOW: return {true,true,512,256*1024}; case Tier::MEDIUM: return {true,true,1024,256*1024}; case Tier::HIGH: return {true,true,2048,256*1024}; case Tier::ULTRA: return {true,true,4096,256*1024}; case Tier::CINEMATIC: return {true,true,8192,256*1024}; }
 return {true,true,512,256*1024};
}
uint32_t streaming_budget(uint32_t){ return 4*1024*1024; }
bool needs_8k(Tier t){ return t==Tier::CINEMATIC; }
}
