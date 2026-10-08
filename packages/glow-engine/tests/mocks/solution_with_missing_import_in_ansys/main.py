# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import junk  # type: ignore  # noqa: F401

from ansys.saf.glow.runtime import glow_main
from ansys.solutions.solution_with_missing_import_in_ansys.solution import definition  # type: ignore


def main():
    glow_main(definition)  # type: ignore


if __name__ == "__main__":
    main()
