// Keyboard flow for the practice slip: focus follows each htmx swap, Shift+Enter marks an answer as
// easy, a held-down Enter can't skip past the feedback, and the word's audio plays on listening
// cards and after each answer (Ctrl+Space or the play button replays it).
(function () {
  'use strict';

  function focusSlip() {
    var target = document.querySelector('#practice [autofocus]');
    if (target) {
      target.focus();
    }
  }

  function playWord() {
    var audio = document.querySelector('#practice audio');
    if (!audio) {
      return;
    }
    var button = document.querySelector('#practice [data-play]');
    audio.currentTime = 0;
    audio.play().catch(function () {
      // Blocked by autoplay rules or no clip for this word: leave the button to try again.
    });
    if (button) {
      audio.onplaying = function () { button.classList.add('is-playing'); };
      audio.onended = audio.onpause = function () { button.classList.remove('is-playing'); };
    }
  }

  document.addEventListener('htmx:afterSettle', function () {
    focusSlip();
    if (document.querySelector('#practice audio[data-autoplay]')) {
      playWord();
    }
  });

  document.addEventListener('click', function (event) {
    if (event.target.closest('#practice [data-play]')) {
      playWord();
      focusSlip();
    }
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === ' ' && event.ctrlKey) {
      event.preventDefault();
      playWord();
      return;
    }
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
