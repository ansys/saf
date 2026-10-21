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

from collections.abc import Callable
import contextlib

import pytest
from selenium import webdriver
from selenium.common.exceptions import InvalidSessionIdException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from ansys.saf.testing._common.common import YieldFixture

DEFAULT_IMPLICIT_WAIT = 10  # seconds
DEFAULT_TIMEOUT = 20  # seconds


@pytest.fixture(scope="session")
def chrome_options(tmp_path_factory: pytest.TempPathFactory) -> Options:
    tmp_path = tmp_path_factory.getbasetemp()
    chrome_options = Options()
    prefs = {"download.default_directory": str(tmp_path)}
    chrome_options.add_experimental_option("prefs", prefs)  # pyright: ignore[reportUnknownMemberType]
    chrome_options.add_argument("--headless")  # pyright: ignore[reportUnknownMemberType]
    chrome_options.add_argument("--no-sandbox")  # pyright: ignore[reportUnknownMemberType]
    chrome_options.add_argument("--disable-dev-shm-usage")  # pyright: ignore[reportUnknownMemberType]
    chrome_options.add_argument("--disable-gpu")  # pyright: ignore[reportUnknownMemberType]
    chrome_options.add_argument("--window-size=1280,800")  # pyright: ignore[reportUnknownMemberType]
    chrome_options.add_argument("--allow-insecure-localhost")  # pyright: ignore[reportUnknownMemberType]
    return chrome_options


@pytest.fixture(scope="session")
def session_selenium_webdriver(chrome_options: Options) -> YieldFixture[WebDriver]:
    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(DEFAULT_IMPLICIT_WAIT)  # type: ignore

    yield driver

    driver.quit()


@pytest.fixture
def selenium_webdriver(chrome_options: Options) -> YieldFixture[WebDriver]:
    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(DEFAULT_IMPLICIT_WAIT)  # type: ignore

    yield driver

    driver.close()


@pytest.fixture
def get_selenium_webdriver(chrome_options: Options) -> YieldFixture[Callable[[], WebDriver]]:
    drivers: list[WebDriver] = []

    def _get_webdriver() -> WebDriver:
        driver = webdriver.Chrome(options=chrome_options)
        drivers.append(driver)
        driver.implicitly_wait(DEFAULT_IMPLICIT_WAIT)  # type: ignore
        return driver

    yield _get_webdriver

    for driver in drivers:
        with contextlib.suppress(InvalidSessionIdException):
            driver.close()


def wait_for_expected_property(
    selenium_webdriver: WebDriver,
    field_id: str,
    property_name: str,
    expected_text: str,
    timeout: int = DEFAULT_TIMEOUT,
    element_type: str = By.ID,
) -> None:
    WebDriverWait(
        selenium_webdriver,
        timeout,
    ).until(  # type: ignore
        lambda x: (
            x.find_element(  # type: ignore
                element_type,
                field_id,
            ).get_property(  # pyright: ignore[reportUnknownMemberType, reportUnknownLambdaType]
                property_name,
            )
            == expected_text
        ),
    )


def wait_for_expected_attribute(
    selenium_webdriver: WebDriver,
    field_id: str,
    attribute_name: str,
    expected_text: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    element_type: str = By.ID,
) -> None:
    WebDriverWait(
        selenium_webdriver,
        timeout,
    ).until(  # type: ignore
        lambda x: (
            x.find_element(  # type: ignore
                element_type,
                field_id,
            ).get_attribute(  # pyright: ignore[reportUnknownMemberType, reportUnknownLambdaType]
                attribute_name,
            )
            == expected_text
        ),
    )


def wait_for_text(
    selenium_webdriver: WebDriver,
    field_id: str,
    expected_text: str,
    timeout: int = DEFAULT_TIMEOUT,
    element_type: str = By.ID,
) -> None:
    WebDriverWait(selenium_webdriver, timeout).until(  # type: ignore
        lambda x: x.find_element(element_type, field_id).text == expected_text,  # type: ignore
    )


def wait_for_text_to_be_different(
    selenium_webdriver: WebDriver,
    field_id: str,
    expected_text: str,
    timeout: int = DEFAULT_TIMEOUT,
    element_type: str = By.ID,
) -> None:
    WebDriverWait(selenium_webdriver, timeout).until(  # type: ignore
        lambda x: expected_text not in x.find_element(element_type, field_id).text,  # type: ignore
    )


def wait_for_element(
    selenium_webdriver: WebDriver,
    element_id: str,
    timeout: int = DEFAULT_TIMEOUT,
    element_type: str = By.ID,
) -> WebElement:
    return WebDriverWait(selenium_webdriver, timeout).until(lambda x: x.find_element(element_type, element_id))  # type: ignore


def wait_for_partial_text(
    selenium_webdriver: WebDriver,
    field_id: str,
    expected_substr: str,
    timeout: int = DEFAULT_TIMEOUT,
    element_type: str = By.ID,
) -> None:
    WebDriverWait(selenium_webdriver, timeout).until(  # type: ignore
        lambda x: expected_substr in x.find_element(element_type, field_id).text,  # type: ignore
    )


def wait_for_element_to_be_clickable(
    selenium_webdriver: WebDriver,
    element_id: str,
    timeout: int = DEFAULT_TIMEOUT,
    element_type: str = By.ID,
) -> None:
    WebDriverWait(selenium_webdriver, timeout).until(  # type: ignore
        expected_conditions.element_to_be_clickable((element_type, element_id)),  # type: ignore
    )


def wait_for_element_and_click(
    selenium_webdriver: WebDriver,
    element_id: str,
    timeout: int = DEFAULT_TIMEOUT,
    element_type: str = By.ID,
) -> None:
    element = wait_for_element(selenium_webdriver, element_id, timeout=timeout, element_type=element_type)
    element.click()


def wait_for_element_and_send_text(
    selenium_webdriver: WebDriver,
    element_id: str,
    input_text: str,
    timeout: int = DEFAULT_TIMEOUT,
    element_type: str = By.ID,
    *,
    clear: bool = False,
) -> None:
    """Type into an element, optionally replacing its value using keyboard events."""
    element = wait_for_element(selenium_webdriver, element_id, timeout=timeout, element_type=element_type)
    if clear:
        # Keyboard events keep React-controlled inputs synchronized with their displayed value.
        element.send_keys(Keys.CONTROL, "a", Keys.NULL, Keys.BACKSPACE)  # type: ignore
    element.send_keys(input_text)  # type: ignore


def move_to_element(
    selenium_webdriver: WebDriver,
    element_id: str,
    timeout: int = 20,
    element_type: str = By.ID,
) -> None:
    element = wait_for_element(selenium_webdriver, element_id, timeout=timeout, element_type=element_type)
    actions = ActionChains(selenium_webdriver)
    # TODO: remove perform?
    actions.move_to_element(element).perform()  # type: ignore
