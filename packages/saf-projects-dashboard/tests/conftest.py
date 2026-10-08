# Copyright (C) 2026 Synopsys, Inc. and ANSYS, Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from pathlib import Path
import time

import pytest

tests_directory = Path(__file__).parent.absolute()
project_directory = Path(__file__).parent.parent.absolute()

DEFAULT_SOLUTION_URL = os.getenv("SAF_SOLUTION_URL", "http://127.0.0.1:61471")


@pytest.fixture(scope="session")
def solution_url():
    """Return the URL of the running SAF solution.

    Set SAF_SOLUTION_URL environment variable to override the default.
    The solution must be running before E2E tests are executed.
    """
    return DEFAULT_SOLUTION_URL


@pytest.fixture(scope="function")
def browser(solution_url):
    """Create a Selenium WebDriver for E2E tests.

    Requires Chrome and ChromeDriver to be installed.
    Uses webdriver-manager for automatic driver management.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
    except ImportError:
        pytest.skip("Selenium is not installed - run: pip install selenium webdriver-manager")

    try:
        from webdriver_manager.chrome import ChromeDriverManager

        service = Service(ChromeDriverManager().install())
    except ImportError:
        service = None
    except Exception as e:
        pytest.skip(f"Could not install ChromeDriver: {e}")

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    try:
        driver = webdriver.Chrome(service=service, options=options) if service else webdriver.Chrome(options=options)
    except Exception as e:
        pytest.skip(f"Could not start Chrome browser: {e}")

    driver.implicitly_wait(10)
    yield driver
    driver.quit()


@pytest.fixture(scope="session")
def project_name():
    """Return a test project name for testing."""
    return f"test_project_{int(time.time())}"
