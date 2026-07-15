/* ============================================================================
   TripJournal — turns a finished itinerary reply into a travel journal.

   Contract (Packaging Studio, business logic frozen):
   - Input: a DOM element whose innerHTML is the marked.js render of the
     planner's UNCHANGED markdown. We only rearrange presentation.
   - Every node of the original content is preserved inside the journal —
     nothing is summarized, dropped, or rewritten.
   - If the reply doesn't look like an itinerary, or anything throws,
     the element is left exactly as it was (graceful fallback).
   ========================================================================== */
(function () {
  'use strict';

  // "Day 3", "Day 3: Munnar", "**Day 3 — Tea Country**", "🗓 Day 3", "### Day 3"
  var DAY_RE = /^\s*(?:[\u{1F300}-\u{1FAFF}☀-➿]\s*)?day\s+(\d{1,2})\s*(?:[:–—-]\s*(.*))?$/iu;

  var TOD_RE = /^(morning|afternoon|evening|night|late night|early morning)\b/i;

  var SECTION_STAMPS = [
    [/budget|cost|expense|price/i, 'Budget'],
    [/pack/i, 'Packing'],
    [/tip|advice|good to know|note/i, 'Tips'],
    [/warn|caution|safety|alert/i, 'Heads-up'],
    [/food|eat|restaurant|cuisine/i, 'Food'],
    [/stay|hotel|accommodation|homestay/i, 'Stays'],
    [/transport|getting|travel between|route/i, 'Transport'],
    [/weather|season|climate/i, 'Season'],
  ];

  function dayInfo(el) {
    // A day marker is a heading (or a paragraph that is ONLY a bold "Day N…")
    var tag = el.tagName;
    var text = (el.textContent || '').trim();
    if (/^H[1-4]$/.test(tag)) {
      var m = text.match(DAY_RE);
      if (m) return { n: +m[1], title: (m[2] || '').trim() };
    }
    if (tag === 'P') {
      var only = el.children.length === 1 && el.children[0].tagName === 'STRONG'
        && el.children[0].textContent.trim() === text;
      if (only) {
        var m2 = text.match(DAY_RE);
        if (m2) return { n: +m2[1], title: (m2[2] || '').trim() };
      }
    }
    return null;
  }

  function stampFor(text) {
    for (var i = 0; i < SECTION_STAMPS.length; i++) {
      if (SECTION_STAMPS[i][0].test(text)) return SECTION_STAMPS[i][1];
    }
    return null;
  }

  function markTimesOfDay(scope) {
    // "**Morning:** …" bolds become small route-colored labels. Presentation only.
    scope.querySelectorAll('strong').forEach(function (s) {
      if (TOD_RE.test(s.textContent.trim())) s.classList.add('j-tod');
    });
  }

  function build(root) {
    var nodes = Array.prototype.slice.call(root.childNodes);

    // ---- segment: preamble | day chapters | closing sections -------------
    var days = [];        // {n, title, nodes[]}
    var pre = [];         // nodes before the first day
    var post = [];        // heading-led sections after the last day
    var current = null;
    var seenDay = false;

    nodes.forEach(function (node) {
      var isEl = node.nodeType === 1;
      var d = isEl ? dayInfo(node) : null;
      if (d) {
        seenDay = true;
        current = { n: d.n, title: d.title, nodes: [] };
        days.push(current);
        return;                              // the marker itself becomes the chapter head
      }
      // A non-day heading AFTER the days closes day content -> closing sections
      if (seenDay && isEl && /^H[1-4]$/.test(node.tagName)) {
        current = null;
        post.push({ head: node, nodes: [] });
        return;
      }
      if (current) current.nodes.push(node);
      else if (seenDay && post.length) post[post.length - 1].nodes.push(node);
      else if (seenDay) { /* stray text right after a day heading group */ post.push({ head: null, nodes: [node] }); }
      else pre.push(node);
    });

    if (days.length < 2) return null;        // not an itinerary — leave untouched

    // ---- hero -------------------------------------------------------------
    var journal = document.createElement('article');
    journal.className = 'journal';

    var hero = document.createElement('header');
    hero.className = 'j-hero';
    var title = '';
    var heroBody = document.createElement('div');
    pre.forEach(function (n) {
      if (!title && n.nodeType === 1 && /^H[1-3]$/.test(n.tagName)) {
        title = n.textContent.trim();        // promote the first heading to the cover
        return;                              // (its text lives on in .j-title)
      }
      heroBody.appendChild(n);
    });
    hero.innerHTML =
      '<div class="j-kicker">Your travel journal · ' + days.length + '-day journey</div>' +
      '<h2 class="j-title"></h2><div class="j-sub md"></div><div class="j-route-line"></div>';
    hero.querySelector('.j-title').textContent = title || 'Your journey, day by day';
    hero.querySelector('.j-sub').appendChild(heroBody);
    journal.appendChild(hero);

    // ---- sticky day navigator (3+ days) ------------------------------------
    var uid = 'j' + Math.random().toString(36).slice(2, 7);
    if (days.length >= 3) {
      var nav = document.createElement('nav');
      nav.className = 'j-nav';
      nav.setAttribute('aria-label', 'Jump to day');
      days.forEach(function (d) {
        var a = document.createElement('a');
        a.href = '#' + uid + '-day-' + d.n;
        a.textContent = 'Day ' + d.n;
        nav.appendChild(a);
      });
      journal.appendChild(nav);
    }

    // ---- day chapters -------------------------------------------------------
    days.forEach(function (d) {
      var sec = document.createElement('section');
      sec.className = 'j-day';
      sec.id = uid + '-day-' + d.n;
      var badge = document.createElement('div');
      badge.className = 'j-day-badge';
      badge.textContent = d.n;
      badge.setAttribute('aria-hidden', 'true');
      // The chapter head is a real disclosure button: long trips fold neatly,
      // everything starts OPEN so nothing is ever hidden by default.
      var head = document.createElement('h3');
      head.className = 'j-day-head';
      var toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'j-day-toggle';
      toggle.setAttribute('aria-expanded', 'true');
      toggle.innerHTML = '<span class="j-day-label">Day ' + d.n + '</span>';
      toggle.appendChild(document.createTextNode(d.title || 'The journey continues'));
      var chev = document.createElement('span');
      chev.className = 'j-chev';
      chev.setAttribute('aria-hidden', 'true');
      toggle.appendChild(chev);
      head.appendChild(toggle);
      var fold = document.createElement('div');
      fold.className = 'j-fold';
      var body = document.createElement('div');
      body.className = 'md j-day-body';
      d.nodes.forEach(function (n) { body.appendChild(n); });
      markTimesOfDay(body);
      fold.appendChild(body);
      toggle.addEventListener('click', function () {
        var open = toggle.getAttribute('aria-expanded') === 'true';
        toggle.setAttribute('aria-expanded', String(!open));
        sec.classList.toggle('j-closed', open);
      });
      sec.appendChild(badge); sec.appendChild(head); sec.appendChild(fold);
      journal.appendChild(sec);
    });

    // ---- closing sections (budget / tips / packing…) ------------------------
    post.forEach(function (s) {
      var hasContent = (s.head && s.head.textContent.trim()) ||
        s.nodes.some(function (n) { return (n.textContent || '').trim(); });
      if (!hasContent) return;
      var sec = document.createElement('section');
      sec.className = 'j-section';
      if (s.head) {
        var headText = s.head.textContent.trim();
        var h = document.createElement('h3');
        h.className = 'j-section-head';
        var st = stampFor(headText);
        if (st) h.innerHTML = '<span class="stamp" aria-hidden="true"></span>';
        if (st) h.querySelector('.stamp').textContent = st;
        h.appendChild(document.createTextNode(headText));
        sec.appendChild(h);
      }
      var body = document.createElement('div');
      body.className = 'md';
      s.nodes.forEach(function (n) { body.appendChild(n); });
      markTimesOfDay(body);
      sec.appendChild(body);
      journal.appendChild(sec);
    });

    // ---- footer: keepsake actions ------------------------------------------
    var footer = document.createElement('footer');
    footer.className = 'j-footer';
    var note = document.createElement('span');
    note.textContent = 'Crafted for you by TripOS — prices are estimates, not booked quotes.';
    footer.appendChild(note);
    var chatEl = document.getElementById('chat');
    var tripId = chatEl && chatEl.dataset ? chatEl.dataset.tripId : '';
    if (tripId) {
      var pdf = document.createElement('a');
      pdf.className = 'btn-ghost text-sm';
      pdf.href = '/trip/' + encodeURIComponent(tripId) + '/print';
      pdf.textContent = 'Download PDF';
      footer.appendChild(pdf);
    }
    journal.appendChild(footer);

    return journal;
  }

  function enhance(el) {
    if (!el || el.dataset.journal) return;
    try {
      // Build from a CLONE: if anything throws mid-transform, the original
      // render is never touched. Only a fully-built journal replaces it.
      var journal = build(el.cloneNode(true));
      if (!journal) return;                   // not an itinerary — untouched
      el.dataset.journal = '1';
      el.innerHTML = '';
      el.appendChild(journal);

      // Highlight the day chips as chapters scroll by.
      var nav = journal.querySelector('.j-nav');
      if (nav && 'IntersectionObserver' in window) {
        var links = {};
        nav.querySelectorAll('a').forEach(function (a) {
          links[a.getAttribute('href').slice(1)] = a;
        });
        var io = new IntersectionObserver(function (entries) {
          entries.forEach(function (en) {
            var a = links[en.target.id];
            if (a) a.classList.toggle('here', en.isIntersecting);
          });
        }, { rootMargin: '-20% 0px -60% 0px' });
        journal.querySelectorAll('.j-day').forEach(function (d) { io.observe(d); });
      }
    } catch (e) {
      // Fallback is sacred: the clone strategy guarantees the original render
      // is still in place — just log and move on.
      if (window.console) console.warn('TripJournal fallback:', e);
    }
  }

  window.TripJournal = { enhance: enhance, _dayRe: DAY_RE };
})();
