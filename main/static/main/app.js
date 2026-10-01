// Keyboard flow for the practice slip: focus follows each htmx swap, Shift+Enter marks an answer as
// easy, and a held-down Enter can't skip past the feedback.
(function () {
  'use strict';

  function focusSlip() {
    var target = document.querySelector('#practice [autofocus]');
    if (target) {
      target.focus();
    }
  }

  document.addEventListener('htmx:afterSettle', focusSlip);

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Enter') {
      return;
    }
    if (event.repeat) {
      event.preventDefault();
      return;
    }
    var input = event.target.closest ? event.target.closest('.answer') : null;
    if (input) {
      input.form.querySelector('[name=easy]').value = event.shiftKey ? '1' : '0';
      return;
    }
    // Enter anywhere outside a form moves on, even if focus has wandered off the button.
    var next = document.querySelector('#practice .btn-next');
    if (next && event.target !== next) {
      event.preventDefault();
      next.click();
    }
  });

  document.addEventListener('htmx:responseError', function (event) {
    var slip = document.getElementById('practice');
    slip.innerHTML = '<p class="eyebrow">Error ' + event.detail.xhr.status + '</p>' +
      '<p class="note">The server could not handle that request. Check the runserver console, then reload the page.</p>';
  });
})();
