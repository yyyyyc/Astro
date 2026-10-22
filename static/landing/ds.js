/* Astro landing design system — field rules shared by every landing form.
 *
 * Declare rules on an input:   data-ds-rules="required date"
 * Optional input mask:          data-ds-mask="date"
 * Optional calendar dialog:     data-ds-picker="date"   (adds a button that opens the native date picker)
 *   data-ds-picker-years-ago="30" — when the field is empty, the dialog opens 30 years before today
 * Each input needs a sibling error element with id "<input id>-error",
 * listed in its aria-describedby. A form may hold one [data-ds-form-error].
 *
 *   DS.bindForm(form, onValid)   — validates on blur/submit, calls onValid(form) when all pass
 *   DS.setFormError(form, msg)   — shows (or clears, with '') a form-level message
 *   DS.dmyToIso('24/03/1988')    — '1988-03-24', or null
 */
(function (global) {
  'use strict';

  const DATE_RE = /^(\d{2})\/(\d{2})\/(\d{4})$/;
  const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/;

  function dmyToIso(str) {
    const m = DATE_RE.exec(String(str || '').trim());
    if (!m) return null;
    const [, d, mo, y] = m;
    const dt = new Date(Date.UTC(+y, +mo - 1, +d));
    if (dt.getUTCFullYear() !== +y || dt.getUTCMonth() !== +mo - 1 || dt.getUTCDate() !== +d) return null;
    return `${y}-${mo}-${d}`;
  }

  // Each rule returns an error message (Hebrew) or '' when the value passes.
  const rules = {
    required(v, input) {
      return v ? '' : (input.dataset.dsRequiredMsg || 'זהו שדה חובה.');
    },
    date(v) {
      if (!v) return '';
      const iso = dmyToIso(v);
      if (!iso) return 'יש להזין תאריך תקין בפורמט יום/חודש/שנה, לדוגמה 24/03/1988.';
      const year = +iso.slice(0, 4);
      if (year < 1900) return 'יש להזין שנה מ-1900 ואילך.';
      if (new Date(iso) > new Date()) return 'תאריך הלידה לא יכול להיות בעתיד.';
      return '';
    },
    email(v) {
      if (!v) return '';
      return v.length <= 254 && EMAIL_RE.test(v) ? '' : 'יש להזין כתובת מייל תקינה, לדוגמה name@example.com.';
    },
  };

  const masks = {
    // Types digits only and inserts the slashes: 24031988 → 24/03/1988
    date(input) {
      input.addEventListener('input', () => {
        const digits = input.value.replace(/\D/g, '').slice(0, 8);
        let v = digits;
        if (digits.length > 4) v = `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
        else if (digits.length > 2) v = `${digits.slice(0, 2)}/${digits.slice(2)}`;
        input.value = v;
      });
    },
  };

  // Calendar button beside a dd/mm/yyyy field; opens the browser's native date dialog
  const pickers = {
    date(input) {
      const wrap = document.createElement('div');
      wrap.className = 'ds-input-wrap';
      input.parentNode.insertBefore(wrap, input);
      wrap.appendChild(input);

      const native = document.createElement('input');
      native.type = 'date';
      native.className = 'ds-input-wrap__native';
      native.tabIndex = -1;
      native.setAttribute('aria-hidden', 'true');
      native.min = input.dataset.dsMin || '1900-01-01';
      native.max = new Date().toISOString().slice(0, 10);

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'ds-input-wrap__action';
      btn.setAttribute('aria-label', 'בחירת תאריך מלוח שנה');
      btn.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">' +
        '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.8"/>' +
        '<path d="M3.5 10h17M8 3v4M16 3v4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
      wrap.append(native, btn);

      btn.addEventListener('click', () => {
        // Open on the typed date, or else on the date data-ds-picker-years-ago years back from today
        let start = dmyToIso(input.value);
        if (!start && input.dataset.dsPickerYearsAgo) {
          const d = new Date();
          d.setFullYear(d.getFullYear() - Number(input.dataset.dsPickerYearsAgo));
          start = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
        }
        native.value = start || '';
        try { native.showPicker(); } catch (e) { native.focus(); native.click(); }
      });
      native.addEventListener('change', () => {
        if (!native.value) return;
        const [y, mo, d] = native.value.split('-');
        input.value = `${d}/${mo}/${y}`;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        validateField(input);
        input.focus();
      });
    },
  };

  function errorEl(input) {
    return document.getElementById(`${input.id}-error`);
  }

  function setFieldError(input, msg) {
    const el = errorEl(input);
    if (el) el.textContent = msg;
    if (msg) input.setAttribute('aria-invalid', 'true');
    else input.removeAttribute('aria-invalid');
  }

  function validateField(input) {
    const v = input.value.trim();
    const names = (input.dataset.dsRules || '').split(/\s+/).filter(Boolean);
    let msg = '';
    for (const name of names) {
      msg = rules[name] ? rules[name](v, input) : '';
      if (msg) break;
    }
    setFieldError(input, msg);
    return !msg;
  }

  function fields(form) {
    return Array.from(form.querySelectorAll('[data-ds-rules]'));
  }

  function validateForm(form) {
    const invalid = fields(form).filter(input => !validateField(input));
    if (invalid.length) invalid[0].focus();
    return invalid.length === 0;
  }

  function setFormError(form, msg) {
    const el = form.querySelector('[data-ds-form-error]');
    if (el) el.textContent = msg || '';
  }

  function bindForm(form, onValid) {
    form.noValidate = true;  // the rules above replace the browser's own (English) bubbles
    fields(form).forEach(input => {
      if (input.dataset.dsMask && masks[input.dataset.dsMask]) masks[input.dataset.dsMask](input);
      if (input.dataset.dsPicker && pickers[input.dataset.dsPicker]) pickers[input.dataset.dsPicker](input);
      // Validate on blur once something was typed; clear the message as soon as the user edits.
      input.addEventListener('blur', () => { if (input.value.trim()) validateField(input); });
      input.addEventListener('input', () => {
        if (input.getAttribute('aria-invalid') === 'true') setFieldError(input, '');
        setFormError(form, '');
      });
    });
    form.addEventListener('submit', e => {
      e.preventDefault();
      setFormError(form, '');
      if (validateForm(form)) onValid(form);
    });
  }

  function setBusy(button, busy) {
    button.disabled = busy;
    if (busy) button.setAttribute('aria-busy', 'true');
    else button.removeAttribute('aria-busy');
  }

  global.DS = { rules, masks, pickers, dmyToIso, validateField, validateForm, setFieldError, setFormError, bindForm, setBusy };
})(window);
