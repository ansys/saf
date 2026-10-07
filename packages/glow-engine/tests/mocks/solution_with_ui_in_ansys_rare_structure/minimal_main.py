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

from ansys.saf.glow.runtime import glow_main
from ansys.solutions.solution_with_ui_in_ansys_rare_structure.my_solution import (  # type: ignore
    my_definition as definition,  # type: ignore
)
from ansys.solutions.solution_with_ui_in_ansys_rare_structure.my_ui import my_app as app  # type: ignore


def main():
    glow_main(definition, app)  # type: ignore


if __name__ == "__main__":
    main()
