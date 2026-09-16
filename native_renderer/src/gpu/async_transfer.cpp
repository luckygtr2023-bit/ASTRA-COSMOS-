#include "async_transfer.h"
namespace astra::gpu {
StagingBuffer create_staging(uint64_t b){ return {b,true}; }
TransferQueue get_transfer_queue(){ return {false,"graphics"}; } // true if transfer queue available
SyncPrimitives get_sync(){ return {3,3,true}; }
bool async_upload(const StagingBuffer&, uint64_t, uint64_t){ return true; /* fences, semaphores, transfer queue if available, else graphics */ }
bool track_lifetime(uint64_t, uint64_t){ return true; }
}
