import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source = readFileSync(new URL('../static/language.js', import.meta.url),'utf8');
function detect({languages=['en'],saved,checked,root='',enabled=true,bot=false,storageError=false}={}) {
  let redirect;
  const storage = { getItem:k=> { if(storageError)throw Error('disabled');return k==='highball-language'?saved:checked; },setItem:()=>{} };
  const config = {languages:['en','es','ru','zh','ja','ko','pt'],detectLanguage:enabled,root};
  vm.runInNewContext(source,{document:{getElementById:()=>({textContent:JSON.stringify(config)})},navigator:{languages,userAgent:bot?'Googlebot':'Browser'},localStorage:storage,sessionStorage:storage,location:{search:'?a=1',hash:'#games',replace:url=>redirect=url}});
  return redirect;
}
for(const language of ['es-AR','ru-RU','zh-CN','ja-JP','ko-KR','pt-BR']) assert.equal(detect({languages:[language]}),`/${language.slice(0,2)}/?a=1#games`);
assert.equal(detect({languages:['fr','ko-KR']}),'/ko/?a=1#games');
assert.equal(detect({languages:['fr','en','es']}),undefined);
assert.equal(detect({languages:['es'],saved:'en'}),undefined);
assert.equal(detect({languages:['en'],saved:'ru',checked:'1'}),'/ru/?a=1#games');
assert.equal(detect({languages:['es'],checked:'1'}),undefined);
assert.equal(detect({languages:['es'],root:'/highball-website'}),'/highball-website/es/?a=1#games');
assert.equal(detect({languages:['es'],enabled:false}),undefined);
assert.equal(detect({languages:['es'],bot:true}),undefined);
assert.equal(detect({languages:['es'],storageError:true}),undefined);
console.log('OK: browser detection for 7 languages, preferences, explicit URLs, unsupported languages, bots, project paths and disabled storage.');
