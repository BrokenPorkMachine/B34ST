#pragma once
// SPDX-License-Identifier: BSD-2-Clause
#include "fbr34ker/types.h"

void shell_init(void);
int shell_execute_line(const char *line);
bool shell_command_name_reserved(const char *name);
NORETURN void shell_run(void);
