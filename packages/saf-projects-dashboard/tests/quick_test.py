# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.

# SPDX-License-Identifier: Apache-2.0
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

"""Quick test to check if ProjectsDashboard loads."""

import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC  # noqa: N812
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager  # pyright: ignore

options = Options()
options.add_argument("--headless=new")  # Run headless for testing
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.set_capability("goog:loggingPrefs", {"performance": "ALL", "browser": "ALL"})

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
try:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5433/projects/69779af0924613b044935dd5"
    print(f"Loading: {url}")
    driver.get(url)
    time.sleep(3)
    print(f"Title: {driver.title}")

    # Navigate to Projects page by clicking in navigation
    print("\nNavigating to Projects page...")
    wait = WebDriverWait(driver, 15)
    try:
        projects_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Projects')]")))
        projects_link.click()
        print("Clicked Projects link")
        time.sleep(5)  # Wait for component to load
    except Exception as e:
        print(f"Could not navigate to Projects: {e}")

    # Check for network requests related to ansys_saf_projects_dashboard
    print("\nNetwork requests for ansys_saf_projects_dashboard:")
    perf_logs = driver.get_log("performance")
    for entry in perf_logs:
        try:
            msg = json.loads(entry.get("message", "{}"))
            method = msg.get("message", {}).get("method", "")
            if "Network.responseReceived" in method:
                response = msg.get("message", {}).get("params", {}).get("response", {})
                url = response.get("url", "")
                status = response.get("status", "")
                if "ansys_saf_projects_dashboard" in url:
                    print(f"  [{status}] {url}")
        except:  # noqa: E722
            pass

    # Check browser console for errors
    logs = driver.get_log("browser")
    print(f"\nBrowser console logs ({len(logs)} entries):")
    for log in logs:
        level = log.get("level", "")
        msg = log.get("message", "")
        if "SEVERE" in level or "ansys_saf_projects_dashboard" in msg.lower() or "error" in msg.lower():
            print(f"  [{level}] {msg[:300]}")

    # Check if window.ansys_saf_projects_dashboard is set
    has_namespace = driver.execute_script("return typeof window.ansys_saf_projects_dashboard !== 'undefined'")
    print(f"\nwindow.ansys_saf_projects_dashboard defined: {has_namespace}")

    # Check what script tags are loaded
    scripts = driver.execute_script(
        """
        return Array.from(document.querySelectorAll('script[src]')).map(s => s.src);
    """,
    )
    print(f"\nScript tags loaded ({len(scripts)} total):")
    for s in scripts:
        if "ansys_saf_projects_dashboard" in s:
            print(f"  FOUND: {s}")

    if not any("ansys_saf_projects_dashboard" in s for s in scripts):
        print("  NO ansys_saf_projects_dashboard scripts found!")

    # Get page source snippet
    source = driver.page_source
    if "projects-dashboard" in source:
        print("\n✓ projects-dashboard found in page source")
    else:
        print("\n✗ projects-dashboard NOT found in page source")

finally:
    driver.quit()
