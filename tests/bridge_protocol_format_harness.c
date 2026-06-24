#include <fbr34ker/abi.h>
#include <fbr34ker/bridge_protocol.h>

int main(void) {
    fbr34ker_bridge_limits_v1 limits = {
        FBR34KER_BRIDGE_PROTOCOL_VERSION,
        FBR34KER_BRIDGE_MAX_MESSAGE_SIZE,
        FBR34KER_BRIDGE_MAX_CHUNK_SIZE,
        FBR34KER_BRIDGE_MAX_MESSAGES,
    };
    if (limits.protocol_version != FBR34KER_BRIDGE_PROTOCOL_VERSION) return 1;
    if (limits.max_message_size != (1024U * 1024U)) return 2;
    if (limits.max_chunk_size > limits.max_message_size) return 3;
    if (limits.max_messages != 4096U) return 4;
    if (FBR34KER_PHYSICAL_SESSION_SCHEMA_VERSION != 1U) return 5;
    return 0;
}
