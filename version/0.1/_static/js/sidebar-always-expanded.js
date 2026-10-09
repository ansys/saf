// The ansys-sphinx-theme (PyData) uses #pst-primary-sidebar / .bd-sidebar-primary
// as the left sidebar container. Force all <details> open and prevent collapsing.


document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('#pst-primary-sidebar details').forEach(function (details) {
    details.setAttribute('open', '');
  });
});
