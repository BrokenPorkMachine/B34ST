#pragma once
#include "fbr34ker/types.h"

void bringup_init(void);
bool bringup_restricted(void);
void bringup_enter(void);
void bringup_exit(void);
bool bringup_command_allowed(const char *name);
const char *bringup_mode_name(void);
