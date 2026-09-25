/*
Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

// The theme's --pst-header-height (used by #pst-primary-sidebar's sticky "top"
// and "max-height") assumes a single-row header. SAF's top navbar has more links
// than fits on one row at common desktop widths, so it wraps onto a second row,
// making the real header taller than that assumed value. This file measures the
// real header height and pins the breadcrumb row and the primary sidebar directly
// below it (matching pyansys-dev-guide, whose single-row header needs no fix-up).
(function () {
  function getHeaderHeight() {
    var header = document.getElementById('pst-header');
    return header ? header.getBoundingClientRect().height : 0;
  }

  // Pin the breadcrumb row directly below the header, however tall it is.
  function syncBreadcrumbStickyOffset() {
    var banner = document.querySelector('.header-nav-banner');
    var headerHeight = getHeaderHeight();
    if (banner) {
      banner.style.top = headerHeight > 0 ? (headerHeight + 'px') : '';
    }
  }

  // Pin the primary sidebar's sticky offset to the header's real (possibly
  // wrapped) height, so it starts right under the header's bottom edge.
  function syncPrimarySidebarOffset() {
    var sidebar = document.getElementById('pst-primary-sidebar');
    var headerHeight = getHeaderHeight();
    if (sidebar) {
      if (headerHeight > 0) {
        sidebar.style.setProperty('--pst-header-height', headerHeight + 'px');
      } else {
        sidebar.style.removeProperty('--pst-header-height');
      }
    }
  }

  // The breadcrumb row sits in normal flow above the sidebar/content grid, pushing
  // the sidebar's un-scrolled position down by the banner's height. Pull the sidebar
  // back up by that same amount so it (and its collapse button) sit flush under the
  // header from the first paint, not only once scrolled past the breadcrumb row. The
  // sidebar and banner share the same background color, so the resulting overlap
  // (see the sidebar's raised z-index in custom.css) is visually seamless.
  function syncPrimarySidebarTopMargin() {
    var sidebar = document.getElementById('pst-primary-sidebar');
    var banner = document.querySelector('.header-nav-banner');
    if (!sidebar) {
      return;
    }
    var bannerHeight = banner ? banner.getBoundingClientRect().height : 0;
    sidebar.style.marginTop = bannerHeight > 0 ? ('-' + bannerHeight + 'px') : '';
  }

  // The theme's default label is "Collapse Sidebar"; SAF uses sentence case.
  function renameCollapseSidebarLabel() {
    var label = document.querySelector('#pst-collapse-sidebar-button .pst-collapse-sidebar-label');
    if (label && label.textContent.trim() === 'Collapse Sidebar') {
      label.textContent = 'Collapse sidebar';
    }
  }

  // SAF hides the "Collapse sidebar" text (see custom.css), showing it as a hover/focus
  // tooltip instead, the same way the theme already shows "Expand sidebar" as a tooltip
  // once the sidebar is squeezed. Reuse the theme's own manual-trigger tooltip instance
  // (via the public getOrCreateInstance API) instead of creating a second, competing one.
  function setupCollapseSidebarTooltip() {
    var button = document.getElementById('pst-collapse-sidebar-button');
    if (!button || typeof bootstrap === 'undefined' || !bootstrap.Tooltip) {
      return;
    }

    function titleForCurrentState() {
      var selector = button.getAttribute('aria-expanded') === 'true'
        ? '.pst-collapse-sidebar-label'
        : '.pst-expand-sidebar-label';
      var label = button.querySelector(selector);
      return label ? label.textContent.trim() : '';
    }

    var tooltip = bootstrap.Tooltip.getOrCreateInstance(button, {
      title: titleForCurrentState,
      trigger: 'manual',
      placement: 'left',
      fallbackPlacements: ['right'],
      offset: [0, 12],
    });
    // Make the title reflect whichever action the button currently performs, even if
    // the theme already created this instance with its own fixed "Expand Sidebar" title.
    if (tooltip._config) {
      tooltip._config.title = titleForCurrentState;
    }

    function showCollapseTooltip() {
      // The theme's own script already shows this tooltip when the sidebar is
      // collapsed; only handle the complementary (expanded/"collapse") state here.
      if (button.getAttribute('aria-expanded') === 'true') {
        tooltip.show();
      }
    }
    function hideCollapseTooltip() {
      tooltip.hide();
    }

    button.addEventListener('mouseenter', showCollapseTooltip);
    button.addEventListener('focus', showCollapseTooltip);
    button.addEventListener('mouseleave', hideCollapseTooltip);
    button.addEventListener('blur', hideCollapseTooltip);
    button.addEventListener('click', hideCollapseTooltip);
  }

  // Keep the breadcrumbs aligned with the article's left edge as the primary sidebar
  // collapses/expands (the article shifts, so the breadcrumb indent must be re-measured).
  function setupBreadcrumbResyncOnSidebarToggle() {
    var button = document.getElementById('pst-collapse-sidebar-button');
    var sidebar = document.getElementById('pst-primary-sidebar');
    if (!button || !sidebar) {
      return;
    }
    // Covers the reduced-motion case, where the width change is instantaneous.
    button.addEventListener('click', function () {
      window.requestAnimationFrame(syncBreadcrumbIndent);
    });
    // Covers the animated case, refining the indent once the width transition settles.
    sidebar.addEventListener('transitionend', function (evt) {
      if (evt.target === sidebar && evt.propertyName === 'width') {
        syncBreadcrumbIndent();
      }
    });
  }

  // The breadcrumb row lives outside the content grid (full-width, between the
  // header and the page), so it can't line up with the article's left edge via
  // CSS alone. Measure the article's actual left edge and indent the breadcrumbs
  // to match, so they sit directly above the page title.
  function syncBreadcrumbIndent() {
    var article = document.querySelector('.bd-article');
    var crumbs = document.querySelector('.header-nav-banner__crumbs');
    if (!article || !crumbs) {
      return;
    }
    var offset = article.getBoundingClientRect().left - crumbs.parentElement.getBoundingClientRect().left;
    if (offset >= 0) {
      crumbs.style.marginLeft = offset + 'px';
    }
  }

  function syncAll() {
    syncBreadcrumbStickyOffset();
    syncPrimarySidebarOffset();
    syncPrimarySidebarTopMargin();
    syncBreadcrumbIndent();
  }

  function rafThrottle(fn) {
    var scheduled = false;
    return function () {
      if (scheduled) return;
      scheduled = true;
      window.requestAnimationFrame(function () {
        scheduled = false;
        fn();
      });
    };
  }

  var syncAllThrottled = rafThrottle(syncAll);

  document.addEventListener('DOMContentLoaded', function () {
    syncAll();
    renameCollapseSidebarLabel();
    setupCollapseSidebarTooltip();
    setupBreadcrumbResyncOnSidebarToggle();
  });
  window.addEventListener('load', syncAll);
  window.addEventListener('resize', syncAllThrottled);
})();
