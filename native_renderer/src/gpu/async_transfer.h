#pragma once
#include <cstdint>
#include <string>
namespace astra::gpu {
struct StagingBuffer { uint64_t size=4*1024*1024; bool host_visible=true; };
struct TransferQueue { bool available=false; std::string name="graphics"; };
struct SyncPrimitives { uint32_t fences=0, semaphores=0; bool timeline=true; };
StagingBuffer create_staging(uint64_t bytes);
TransferQueue get_transfer_queue();
SyncPrimitives get_sync();
bool async_upload(const StagingBuffer& staging, uint64_t dst, uint64_t size); // fences/semaphores, non-blocking graphics queue
bool track_lifetime(uint64_t id, uint64_t frame);
}
