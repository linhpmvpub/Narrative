'use strict';
const $=id=>document.getElementById(id);let token='',epoch=0,source=null;
function el(tag,text){const n=document.createElement(tag);n.textContent=text;return n;}
async function api(path,method='GET',body){const r=await fetch('/api/v0/'+path,{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json','Idempotency-Key':crypto.randomUUID()},body:body?JSON.stringify(body):undefined,cache:'no-store'});const data=await r.json();if(!r.ok)throw new Error(data.message||(typeof data.detail==='string'?data.detail:'Không thực hiện được yêu cầu'));return data;}
async function run(fn){try{await fn();}catch(e){$('notice').textContent=e.message;}}
async function reload(){$('result').textContent='';const gen=++epoch;const [news,list]=await Promise.all([api('news?limit=200'),api('news-claims')]);if(gen!==epoch)return;$('login').hidden=true;$('workspace').hidden=false;const selected=$('item').value;$('item').replaceChildren();for(const item of news.items)$('item').append(new Option(item.title,item.id));if(selected)$('item').value=selected;$('canonical-panel').hidden=list.role!=='admin';$('dossier-panel').hidden=list.role!=='admin';$('dossier-result').replaceChildren();$('snapshot-result').textContent='';$('claims').replaceChildren();for(const claim of list.items){const box=el('article','');box.className='news-card';box.append(el('h3',claim.payload.ticker+' · '+claim.status),el('p',claim.payload.claim.claim_text),el('p','Phiên bản quyết định: '+claim.review_version));if(claim.ingestion_receipt)box.append(el('p','Canonical: '+claim.ingestion_status+' · '+claim.ingestion_receipt.event_id));if(claim.blocker)box.append(el('p',claim.blocker));if(list.role==='admin'){const form=el('form','');const decision=el('select','');for(const [value,label] of [['','Chọn quyết định'],['approved','Phê duyệt'],['rejected','Từ chối'],['revoked','Thu hồi phê duyệt']])decision.append(new Option(label,value));decision.required=true;const kind=el('select','');kind.required=true;for(const [v,l] of [['','Loại người duyệt'],['human_declared','Người dùng tự khai'],['AI_SIMULATED','Agent AI']])kind.append(new Option(l,v));form.append(decision,kind);const checks={};for(const [key,label] of [['identity_confirmed','Đã đối chiếu đúng công ty'],['citation_confirmed','Đã kiểm tra đoạn nguồn và URL'],['comparison_confirmed','Đã kiểm tra đơn vị/kỳ so sánh hoặc xác nhận không áp dụng']]){const line=el('label',label);const input=el('input','');input.type='checkbox';line.prepend(input);checks[key]=input;form.append(line);}const reason=el('textarea','');reason.required=true;reason.minLength=20;reason.placeholder='Lý do kiểm duyệt, bằng chứng và giới hạn';form.append(reason,el('button','Lưu quyết định'));form.addEventListener('submit',e=>{e.preventDefault();run(async()=>{await api('news-claims/'+claim.id+'/reviews','POST',{expected_review_version:claim.review_version,decision:decision.value,reviewer_kind:kind.value,rationale:reason.value,...Object.fromEntries(Object.entries(checks).map(([k,v])=>[k,v.checked]))});if(gen===epoch)await reload();});});box.append(form);if(claim.status==='approved'){const prepare=el('button','Chuẩn bị intake (chưa tạo sự kiện)');prepare.type='button';prepare.addEventListener('click',()=>run(async()=>{const r=await api('news-claims/'+claim.id+'/prepare','POST',{});if(gen===epoch){$('result').textContent=JSON.stringify(r,null,2);box.querySelector('.canonical-form')?.remove();if(!claim.ingestion_receipt)box.append(canonicalForm(claim,r,list.items,gen));}}));box.append(prepare);}}if(claim.ingestion_receipt&&claim.status==='approved'){const exposure=el('button','Thẩm định tỷ trọng phân khúc');exposure.type='button';const panel=el('div','');exposure.addEventListener('click',()=>run(()=>loadExposure(claim.id,panel,gen)));box.append(exposure,panel);}$('claims').append(box);}$('notice').textContent='Đã tải claim; thông báo thật tắt.';}
$('login').addEventListener('submit',e=>{e.preventDefault();epoch++;token=$('token').value.trim();$('token').value='';run(reload);});
$('load').addEventListener('click',()=>run(async()=>{const gen=epoch;const value=await api('news-claims/source/'+encodeURIComponent($('item').value));if(gen!==epoch)return;source=value;source.item_id=$('item').value;$('dossier-result').replaceChildren();$('source').value=value.text;$('claim-json').value='';$('quote-preview').value='';$('notice').textContent='Đã khóa nguồn v'+value.version+' cho bản nháp này.';}));
$('quote').addEventListener('click',()=>{if(!source)return;let start=$('source').selectionStart,end=$('source').selectionEnd;while(start<end&&/\s/.test(source.text[start]))start++;while(end>start&&/\s/.test(source.text[end-1]))end--;if(end<=start){$('notice').textContent='Hãy chọn một đoạn nguồn.';return;}$('quote-preview').value=source.text.slice(start,end);$('claim-json').value=JSON.stringify({claim_text:source.text.slice(start,end),metric_id:null,unit:null,period:null,comparison_basis:'qualitative excerpt only; numerical comparison not asserted',old_value:null,new_value:null,source_span:{start,end},source_url:source.url,old_basis:null,new_basis:null},null,2);});
$('draft').addEventListener('submit',e=>{e.preventDefault();run(async()=>{if(!source||!$('claim-json').value)throw new Error('Đọc nguồn và chọn đoạn trích trước khi lập claim.');const gen=epoch;await api('news-claims','POST',{revision_id:source.revision_id,expected_payload_sha256:source.payload_sha256,ticker:$('ticker').value,event_type:$('event').value,author_kind:$('author-kind').value,claim:JSON.parse($('claim-json').value),comparison_period:$('prior-period').value||null,uncertainties:[$('uncertainty').value]});if(gen===epoch)await reload();});});
$('reload').addEventListener('click',()=>run(reload));$('logout').addEventListener('click',()=>{epoch++;token='';source=null;$('token').value='';$('workspace').hidden=true;$('login').hidden=false;for(const id of ['source','claim-json','quote-preview','uncertainty','prior-period','snapshot-at'])$(id).value='';for(const id of ['claims','result','item','snapshot-result','dossier-result'])$(id).replaceChildren();$('notice').textContent='Đã xóa mã và nội dung khỏi trang.';});

function field(form,label,control){const wrap=el('label',label);wrap.append(control);form.append(wrap);return control;}
function canonicalForm(claim,intake,items,gen){
 const form=el('form','');form.className='canonical-form';form.append(el('h4','Nhập sự kiện canonical'),el('p','Xác nhận danh tính sự kiện. Chưa đánh giá tác động; thông báo thật tắt.'));
 const action=field(form,'Cách nhập',el('select',''));action.name='action';action.required=true;
 for(const [v,t] of [['','Chọn cách nhập'],['new','Sự kiện mới'],['duplicate','Bài trùng'],['correction','Bản sửa']])action.append(new Option(t,v));
 const target=field(form,'Claim đã nhập làm bản gốc',el('select',''));target.name='target';target.append(new Option('Chọn bản gốc',''));
 for(const c of items.filter(c=>c.ingestion_receipt&&c.id!==claim.id))target.append(new Option(c.id+' · '+c.payload.ticker+' · '+c.payload.claim.claim_text.slice(0,80),c.id));
 const targetId=field(form,'Hoặc nhập ID claim bản gốc ngoài danh sách',el('input',''));targetId.name='target_id';targetId.maxLength=100;
 const occurrence=field(form,'Mốc / định danh lần xảy ra',el('input',''));occurrence.name='occurrence_window';occurrence.required=true;occurrence.minLength=10;occurrence.maxLength=200;
 const note=field(form,'Căn cứ xác nhận cùng hoặc khác sự kiện',el('textarea',''));note.name='identity_note';note.required=true;note.minLength=20;note.maxLength=4000;
 const confirmed=el('input','');confirmed.type='checkbox';confirmed.name='identity_confirmed';confirmed.required=true;field(form,'Đã đối chiếu danh tính, metric, kỳ và bản gốc',confirmed);
 const button=el('button','Ghi canonical');form.append(button);
 function mode(){const isNew=action.value==='new';target.disabled=isNew;targetId.disabled=isNew;if(isNew){target.value='';targetId.value='';}confirmed.checked=false;}
 action.addEventListener('change',mode);
 target.addEventListener('change',()=>{targetId.value='';const c=items.find(c=>c.id===target.value);if(c?.ingestion_identity)occurrence.value=c.ingestion_identity.occurrence_window;confirmed.checked=false;});
 for(const input of [targetId,occurrence,note])input.addEventListener('input',()=>{confirmed.checked=false;});
 form.addEventListener('submit',e=>{e.preventDefault();run(async()=>{
   if(gen!==epoch)return;const targetValue=targetId.value.trim()||target.value;
   if(action.value!=='new'&&!targetValue)throw new Error('Chọn hoặc nhập ID claim bản gốc.');
   button.disabled=true;
   try{const result=await api('news-claims/'+claim.id+'/ingest','POST',{
     expected_intake_sha256:intake.payload_sha256,occurrence_window:occurrence.value.trim(),
     identity_note:note.value.trim(),identity_confirmed:confirmed.checked,
     action:action.value,target_claim_id:action.value==='new'?null:targetValue});
     if(gen!==epoch)return;await reload();if(epoch===gen+1)$('result').textContent=JSON.stringify(result,null,2);
   }finally{button.disabled=false;}
 });});return form;
}
$('snapshot-form').addEventListener('submit',e=>{e.preventDefault();run(async()=>{
 const gen=epoch,cutoff=$('snapshot-at').value.trim();$('snapshot-result').textContent='';
 const result=await api('news-claims/canonical'+(cutoff?'?as_of='+encodeURIComponent(cutoff):''));
 if(gen===epoch)$('snapshot-result').textContent=JSON.stringify(result,null,2);
});});

$('ticker').addEventListener('change',()=>{$('dossier-result').replaceChildren();});
$('load-dossier').addEventListener('click',()=>run(async()=>{
 if(!source)throw new Error('Đọc phiên bản nguồn trước khi đối chiếu.');
 const gen=epoch,revision=source.revision_id,ticker=$('ticker').value;
 $('dossier-result').replaceChildren();
 const d=await api('news-claims/source/'+encodeURIComponent(source.item_id)+'/dossier?ticker='+encodeURIComponent(ticker)+'&expected_payload_sha256='+source.payload_sha256);
 if(gen!==epoch||source?.revision_id!==revision||$('ticker').value!==ticker)return;
 const root=$('dossier-result');root.append(el('p','Nguồn v'+d.source.version+' · Số liệu có sẵn trước '+d.evidence_cutoff),el('p','Mức phơi nhiễm và materiality: chưa xác định. Quan hệ nhân quả: chưa xác minh.'));
 const raw=d.raw_source_evidence;if(raw){root.append(el('p','Bản RSS: '+raw.status+' · Hash: '+raw.capture_sha256),el('p','Kiểm tra file hiện có, không chứng minh thời điểm lưu ban đầu. Bằng chứng bài viết: chưa đính kèm. Không phải xác minh độc lập hay phê duyệt tác động.'));}
 root.append(el('h3','Số liệu tài chính nền'));
 if(!d.financial_context.length)root.append(el('p','Chưa có số liệu nền hợp lệ trước thời điểm nhận tin.'));
 for(const c of d.financial_context){const box=el('article','');box.className='news-card';box.append(el('h4',c.label||c.metric),el('p',c.current.start+' → '+c.current.end+': '+c.current.value+' '+c.unit),el('p','Kỳ so sánh '+c.prior.start+' → '+c.prior.end+': '+c.prior.value+' '+c.unit));const a=el('a','Hồ sơ SEC');try{const u=new URL(c.filing_url);if(u.protocol==='https:'){a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';box.append(a);}}catch{}root.append(box);}
 root.append(el('p','Bản ghi phân khúc có nguồn: '+d.segment_context.length+(d.truncated?' · Kết quả đã giới hạn':'')));
 const details=el('details','');details.append(el('summary','Chi tiết nguồn, phân khúc và bằng chứng còn thiếu'),el('pre',JSON.stringify(d,null,2)));root.append(details);
}));

async function loadExposure(claimId,root,gen){
 root.replaceChildren();const data=await api('news-claims/'+claimId+'/exposure');if(gen!==epoch)return;root.replaceChildren();
 root.append(el('p','Tỷ trọng doanh thu nền, không phải phần doanh thu bị ảnh hưởng. Materiality và tác động giá vẫn chưa xác định.'));
 if(!data.pairs.length)root.append(el('p','Chưa có cặp phân khúc/hợp nhất cùng hồ sơ, kỳ, đơn vị và khái niệm phù hợp.'));
 if(data.pairs.length){
  const form=el('form','');form.className='exposure-draft';
  const pair=field(form,'Cặp bằng chứng',el('select',''));pair.required=true;pair.append(new Option('Chọn cặp số liệu',''));
  for(const p of data.pairs)pair.append(new Option(p.numerator.segment+' · '+p.numerator.current.start+' → '+p.numerator.current.end+' · '+p.numerator.current.value+'/'+p.denominator.current.value+' '+p.denominator.unit+' = '+p.percent+'%',p.pair_sha256));
  const evidence=el('pre','');form.append(evidence);pair.addEventListener('change',()=>{evidence.textContent=JSON.stringify(data.pairs.find(p=>p.pair_sha256===pair.value)||{},null,2);});
  const kind=field(form,'Người lập',el('select',''));kind.required=true;for(const [v,l] of [['','Chọn loại'],['human_declared','Người dùng tự khai'],['AI_SIMULATED','Agent AI']])kind.append(new Option(l,v));
  const rationale=field(form,'Vì sao tin liên quan phân khúc này? Dẫn bằng chứng',el('textarea',''));rationale.required=true;rationale.minLength=20;
  const limits=field(form,'Giới hạn và phần ảnh hưởng chưa biết',el('textarea',''));limits.required=true;limits.minLength=20;
  form.append(el('button','Lưu bản thẩm định'));
  form.addEventListener('submit',e=>{e.preventDefault();run(async()=>{if(gen!==epoch)return;await api('news-claims/'+claimId+'/exposure','POST',{pair_sha256:pair.value,author_kind:kind.value,news_link_rationale:rationale.value,limitations:limits.value});if(gen===epoch)await loadExposure(claimId,root,gen);});});root.append(form);
 }
 for(const d of data.drafts){
  const box=el('article','');box.className='news-card';box.append(el('h4','Thẩm định: '+d.status+' · quyết định v'+d.review_version),el('p',d.payload.news_link_rationale),el('p',d.payload.limitations));
  if(data.role==='admin'){
   const form=el('form','');form.className='exposure-review';
   const decision=field(form,'Quyết định',el('select',''));decision.required=true;for(const [v,l] of [['','Chọn quyết định'],['approved','Phê duyệt tỷ trọng nền'],['rejected','Từ chối'],['revoked','Thu hồi']])decision.append(new Option(l,v));
   const kind=field(form,'Người duyệt',el('select',''));kind.required=true;for(const [v,l] of [['','Chọn loại'],['human_declared','Người dùng tự khai'],['AI_SIMULATED','Agent AI']])kind.append(new Option(l,v));
   const checks={};for(const [k,l] of [['periods_units_scope_confirmed','Đã kiểm tra kỳ, đơn vị, phạm vi và nguồn'],['news_link_reviewed','Đã đối chiếu căn cứ liên quan giữa tin và phân khúc'],['baseline_not_effect_confirmed','Tỷ trọng nền không phải tác động do tin gây ra']]){const input=el('input','');input.type='checkbox';checks[k]=field(form,l,input);}
   const rationale=field(form,'Lý do quyết định',el('textarea',''));rationale.required=true;rationale.minLength=20;form.append(el('button','Lưu quyết định tỷ trọng'));
   form.addEventListener('submit',e=>{e.preventDefault();run(async()=>{if(gen!==epoch)return;await api('news-claims/exposure/'+d.id+'/reviews','POST',{expected_version:d.review_version,decision:decision.value,reviewer_kind:kind.value,rationale:rationale.value,...Object.fromEntries(Object.entries(checks).map(([k,v])=>[k,v.checked]))});if(gen===epoch)await loadExposure(claimId,root,gen);});});box.append(form);
  }root.append(box);
 }
}
