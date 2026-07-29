(function(){
  var list=document.getElementById('pfMarketList'),toggle=document.getElementById('pfMarketToggle');
  if(list&&toggle){toggle.addEventListener('click',function(){var open=list.classList.toggle('expanded');toggle.setAttribute('aria-expanded',String(open));toggle.textContent=open?'Show fewer markets -':'Show more markets +';});}
  document.querySelectorAll('.pf-faq-q').forEach(function(button){button.addEventListener('click',function(){var item=button.closest('.pf-faq-item'),wasOpen=item.classList.contains('open');document.querySelectorAll('.pf-faq-item').forEach(function(entry){entry.classList.remove('open');entry.querySelector('.pf-faq-q').setAttribute('aria-expanded','false');entry.querySelector('.pf-faq-a').hidden=true;});if(!wasOpen){item.classList.add('open');button.setAttribute('aria-expanded','true');item.querySelector('.pf-faq-a').hidden=false;}});});
})();
