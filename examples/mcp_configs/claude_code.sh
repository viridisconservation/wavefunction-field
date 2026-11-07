#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Register the agent-side server with Claude Code.
claude mcp add wavefunction-field --env WF_FIELD_URL=http://127.0.0.1:8787 -- wf-agent
