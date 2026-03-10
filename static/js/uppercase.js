// Uppercase helper: force inputs and textareas to uppercase on input and paste
(function(){
  function toUpperInput(el){
    try{
      const start = el.selectionStart;
      const end = el.selectionEnd;
      el.value = el.value.toUpperCase();
      if(typeof start === 'number' && typeof end === 'number') el.setSelectionRange(start, end);
    }catch(e){ /* ignore */ }
  }

  document.addEventListener('input', function(e){
    const t = e.target;
    if(!t) return;
    const tag = t.tagName && t.tagName.toUpperCase();
    if(tag === 'INPUT'){
      const type = (t.type || '').toLowerCase();
      if(type === 'text' || type === 'search' || type === 'tel' || type === 'email'){
        toUpperInput(t);
      }
    } else if(tag === 'TEXTAREA'){
      toUpperInput(t);
    }
  }, true);

  document.addEventListener('paste', function(e){
    const t = e.target;
    if(!t) return;
    const tag = t.tagName && t.tagName.toUpperCase();
    if(tag === 'INPUT' || tag === 'TEXTAREA'){
      setTimeout(function(){ toUpperInput(t); }, 0);
    }
  });
})();
