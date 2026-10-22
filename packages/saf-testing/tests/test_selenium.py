# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
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

from unittest.mock import Mock, call

import pytest
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement

from ansys.saf.testing.selenium import wait_for_element_and_send_text


@pytest.mark.parametrize("clear", [False, True])
def test_wait_for_element_and_send_text(clear: bool) -> None:
    driver = Mock(spec=WebDriver)
    element = Mock(spec=WebElement)
    driver.find_element.return_value = element

    wait_for_element_and_send_text(driver, "argument", "3", clear=clear)

    driver.find_element.assert_called_once_with(By.ID, "argument")
    expected_calls = [call("3")]
    if clear:
        expected_calls.insert(0, call(Keys.CONTROL, "a", Keys.NULL, Keys.BACKSPACE))
    assert element.send_keys.call_args_list == expected_calls


def test_wait_for_element_and_send_text_appends_by_default() -> None:
    driver = Mock(spec=WebDriver)
    element = Mock(spec=WebElement)
    driver.find_element.return_value = element

    wait_for_element_and_send_text(driver, "//input", "4", element_type=By.XPATH)

    driver.find_element.assert_called_once_with(By.XPATH, "//input")
    element.send_keys.assert_called_once_with("4")
