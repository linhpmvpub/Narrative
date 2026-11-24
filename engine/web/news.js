'use strict';
let articleResult=null,readingVersion=null;
function clearReading(){readingVersion=null;$('reading-tickers').replaceChildren();$('reading-narratives').replaceChildren();$('save-reading').disabled=true;$('reading-status').textContent='';$('reading-preferences').open=false;}
async function loadReading(){const gen=epoch;$('save-reading').disabled=true;try{const data=await api('/article-preferences');if(gen!==epoch||!token)return;readingVersion=data.version;
 for(const [rootId,selected,available] of [['reading-tickers',data.tickers,data.catalog.tickers.map(t=>[t,t])],['reading-narratives',data.narratives,data.catalog.narratives.map(n=>[n.id,n.ticker+' · '+n.title])]]){
 const root=$(rootId);root.replaceChildren();const choices=new Map(available);for(const key of selected)if(!choices.has(key))choices.set(key,key+' · hiện không có trong hồ sơ');
 for(const [key,title] of choices){const label=el('label',title);const box=document.createElement('input');box.type='checkbox';box.value=key;box.checked=selected.includes(key);label.prepend(box);root.append(label);}}
 $('following-only').checked=data.following_only;$('include-archive').checked=data.include_archive;$('save-reading').disabled=false;$('reading-status').textContent=data.catalog.available?'Lựa chọn hiện tại đã tải.':'Hồ sơ tạm không khả dụng; có thể giữ hoặc bỏ lựa chọn cũ.';
 }catch(e){if(gen===epoch)$('reading-status').textContent=e.message;}}

function renderArticles(result){
 articleResult=result;const root=$('article-list');root.replaceChildren();
 if(!result){root.append(el('p','Không kiểm tra được nguồn; đã ẩn thẻ toàn bài.','stale'));return;}
 if(!result.enabled){root.append(el('p','Chưa bật thẻ toàn bài cho phiên này.'));return;}
 const ts=$('article-ticker'),ns=$('article-narrative'),ticker=ts.value,narrative=ns.value;
 ts.replaceChildren(new Option('Tất cả',''));ns.replaceChildren(new Option('Tất cả',''));
 for(const t of [...new Set(result.items.map(c=>c.ticker))].sort())ts.append(new Option(t,t));
 if([...ts.options].some(o=>o.value===ticker))ts.value=ticker;
 const narratives=new Map(result.items.filter(c=>!ts.value||c.ticker===ts.value).map(c=>[c.profile_id+':'+c.narrative_id,c.narrative]));
 for(const [id,label] of narratives)ns.append(new Option(label,id));
 if(narratives.has(narrative))ns.value=narrative;
 root.append(el('p',(result.held_articles||0)+' bài đang giữ lại để kiểm tra / duyệt lại','meta'));
 const cards=result.items.filter(c=>(!ts.value||c.ticker===ts.value)&&(!ns.value||c.profile_id+':'+c.narrative_id===ns.value));
 if(!cards.length)root.append(el('p','Không có thẻ còn đủ điều kiện trong lựa chọn này.'));
 for(const c of cards){const box=el('article','','news-card');box.dataset.cardId=c.id;
 box.append(el('p',c.priority_reason==='NARRATIVE_FOLLOWED'?'Ưu tiên: narrative bạn theo dõi':c.priority_reason==='COMPANY_FOLLOWED'?'Ưu tiên: công ty bạn theo dõi':'Khám phá thêm','meta'),el('h3',c.headline),el('p',c.ticker+' · '+c.narrative),el('p',c.freshness==='ARCHIVE_CONTEXT'?'Ngữ cảnh lịch sử · không phải tin mới':'Trong cửa sổ thời gian của hồ sơ','meta'),el('blockquote',c.summary),el('p','Vì sao liên quan: '+c.why_relevant));
 const d=el('details');d.append(el('summary','Đường liên quan và bằng chứng'));
 for(const edge of c.path){d.append(el('p',c.nodes[edge.from_id]+' → '+c.nodes[edge.to_id]+' · '+edge.scope));for(const e of edge.evidence)d.append(el('blockquote',e.quote),profileLink({id:e.source_id,url:c.profile_sources[e.source_id]}));}
 for(const u of c.unknowns)d.append(el('p','Chưa biết: '+u));box.append(d,profileLink({id:'bài gốc',url:c.url}),el('p','Nguồn: '+date(c.published_at)+' · Hồ sơ v'+c.profile_version+' · Tác động chưa xác minh','meta'));root.append(box);
 }
}
function renderRoleNews(result,operating=false){
 const root=$(operating?'reviewed-operation-list':'reviewed-role-list');root.replaceChildren();
 if(!result){root.append(el('p','Không kiểm tra được bằng chứng; đã ẩn dữ liệu.','stale'));return;}
 if(!result.items.length){root.append(el('p','Chưa có trích đoạn đã kiểm duyệt còn đủ bằng chứng cho khu vực này.'));return;}
 for(const item of result.items){const box=el('article','','news-card');box.dataset.cardId=item.id;
 box.append(el('h3',item.headline),el('p',item.ticker+' · '+item.narrative_title),el('blockquote',item.excerpt),el('p','Nguồn phát hành: '+item.issuer+' · Ngày hồ sơ: '+date(item.published_at)+' · Phiên bản '+item.version+' · '+(item.reviewer_kind==='AI_INDEPENDENT'?'Kiểm duyệt AI độc lập':'Kiểm duyệt được ghi nhận'),'meta'));
 for(const r of item.roles)box.append(el('p','Bên mua theo nguồn: '+item.issuer+' · Sản phẩm: '+r.product+' · Danh sách nhà cung cấp được nêu: '+r.supplier_text));
 const detail=el('details');detail.append(el('summary',operating?'Xem hoạt động, đường liên quan và kiểm tra hiệu lực':'Xem vai trò, đường liên quan và kiểm tra hiệu lực'));
 for(const link of item.links){detail.append(el('p',link.scope));for(const edge of link.path){detail.append(el('p',edge.from+' → '+edge.to+' · '+edge.scope));for(const e of edge.evidence)detail.append(el('blockquote',e.quote));}}
 for(const line of item.decision_trace)detail.append(el('p',line));for(const source of item.profile_sources)detail.append(profileLink(source),el('br'));
 box.append(detail,profileLink({id:'SEC',url:item.source_url}),el('p',operating?'Thông tin hoạt động do chính doanh nghiệp công bố. Tác động tài chính: chưa biết. Thông báo thật tắt.':'Đã kiểm duyệt trích đoạn; chưa hợp nhất danh tính hay xác minh quan hệ hiện tại. Tác động: chưa biết. Thông báo thật tắt.','stale'));root.append(box);}
}

function renderProfileNews(result){
 const root=$('rss-profile-list');root.replaceChildren();
 if(!result){root.append(el('p','Không kiểm tra được tin theo yếu tố; đã ẩn dữ liệu.','stale'));return;}
 root.append(el('p','Đối chiếu '+(result.examined||0)+' mục RSS · '+result.items.length+' thẻ liên quan'+(result.truncated?' · Kết quả có giới hạn':''),'meta'));
 if(!result.items.length)root.append(el('p','Chưa có tin khớp các yếu tố còn đủ bằng chứng.'));
 for(const card of result.items){const box=el('article','','news-card');box.dataset.cardId=card.id;
  box.append(el('h3',card.headline),el('p','RSS CHƯA XÁC MINH · Gợi ý liên quan, không kết luận tác động','stale'),el('p',card.excerpt),el('p',card.ticker+' · '+card.narrative_title),el('p','Mốc nguồn: '+date(card.published_at)+' · Ghép được từ: '+date(card.available_at),'meta'));
  for(const item of card.links){box.append(el('h4','Vì sao đáng theo dõi: '+item.factor));const flow=el('ol');for(const r of item.path)flow.append(el('li',r.from+' → '+r.to));box.append(flow,el('p',item.scope));const detail=el('details');detail.append(el('summary','Xem điều kiện, từ khớp và nguồn hồ sơ'));
   for(const r of item.path){for(const c of r.conditions)detail.append(el('p','Điều kiện: '+c));for(const u of r.unknowns)detail.append(el('p','Chưa biết: '+u));for(const e of r.evidence)detail.append(el('blockquote',e.quote));}
   detail.append(el('p','Từ khớp trong RSS: '+item.matches.map(m=>m.text+' ('+(m.field==='title'?'tiêu đề':'trích đoạn')+')').join(' · ')));
   if(item.entity_context){const ref=item.entity_context;detail.append(el('h4','Tên tổ chức và phạm vi nhận diện'),el('p',ref.label+' · '+(ref.resolution==='CONTEXT_ONLY'?'Chỉ liên hệ ngữ cảnh; chưa xác định pháp nhân trong tin':'Tham chiếu pháp nhân theo hồ sơ; bên được nói đến trong tin chưa xác minh'),'stale'),el('p',ref.scope));for(const u of ref.unknowns)detail.append(el('p','Chưa biết: '+u));for(const e of ref.evidence)detail.append(el('blockquote',e.quote));for(const r of item.entity_context_path||[])detail.append(el('p','Đường ngữ cảnh: '+r.from+' → '+r.to+' · '+r.scope));}
   for(const e of item.profile_evidence)detail.append(el('blockquote',e.quote));for(const src of item.sources)detail.append(profileLink(src),el('br'));box.append(detail);
  }
  for(const u of card.unknowns)box.append(el('p','Chưa biết: '+u,'meta'));
  box.append(el('p','Hồ sơ v'+card.profile_version+' · Nguồn nền: '+date(card.profile_snapshot_at)+' · '+card.news_revisions.length+' mục RSS cùng bài đã gộp','meta'));
  if(card.news_revisions.some(r=>r.capture_proof==='NOT_ARCHIVED'))box.append(el('p','Bản chụp RSS gốc của mục tin này chưa được lưu; nội dung vẫn chưa xác minh.','meta'));
  const revisions=el('details');revisions.append(el('summary','Nguồn và phiên bản tin'));for(const r of card.news_revisions)revisions.append(el('p',r.source_name+' · v'+r.version));box.append(revisions,profileLink({id:'RSS',url:card.url}),el('p','Thông báo thật tắt · Tác động giá và quy mô tài chính: chưa biết.','meta'));root.append(box);
 }
}
function profileLink(source){const a=document.createElement('a');a.textContent='Nguồn '+source.id+' ↗';try{const u=new URL(source.url);if(u.protocol==='https:'){a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';}}catch{}return a;}
function renderProfiles(result){
 const root=$('profile-list');root.replaceChildren();
 if(!result){root.append(el('p','Không kiểm tra được hồ sơ; đã ẩn dữ liệu.','stale'));return;}
 if(!result.items.length){root.append(el('p','Chưa có hồ sơ còn đủ bằng chứng.','meta'));return;}
 if(result.truncated)root.append(el('p','Chỉ xét 30 hồ sơ đầu tiên.','meta'));
 const status={SOURCED:'Có nguồn',UNKNOWN:'Chưa biết',NOT_DISCLOSED:'Không công bố',NOT_APPLICABLE:'Không áp dụng',STALE:'Đã cũ',DISPUTED:'Có mâu thuẫn'};
 const stance={RELATED_INFORMATION:'Thông tin liên quan',SUPPORTS_ASSUMPTION:'Hỗ trợ giả định',CHALLENGES_ASSUMPTION:'Thách thức giả định',MIXED:'Thông tin theo cả hai hướng'};
 for(const profile of result.items){
  const overview=el('details');overview.append(el('summary',profile.ticker+' · Hồ sơ v'+profile.version+' · '+(profile.coverage.SOURCED||0)+'/'+profile.components.length+' thành phần có nguồn'));
  overview.append(el('p',profile.description),el('p','Ảnh chụp lịch sử: '+date(profile.snapshot_at)));
  for(const c of profile.components){const part=el('details');part.append(el('summary',(result.component_catalog[c.key]||c.key)+' · '+status[c.status]),el('p',c.summary));for(const e of c.evidence)part.append(el('blockquote',e.quote));overview.append(part);}for(const source of profile.sources)overview.append(profileLink(source),el('br'));root.append(overview);
  for(const card of profile.cards){const box=el('article','','news-card');box.append(el('h3',card.headline),el('p',card.historical?'MẪU LỊCH SỬ · AI trích nguồn · không phải tin mới':'HỒ SƠ NGHIÊN CỨU · AI trích nguồn','stale'),el('p',card.summary),el('h4','Vì sao liên quan?'),el('p',card.narrative.title+' · '+stance[card.stance]));
   const chain=el('ol');for(const r of card.path)chain.append(el('li',r.from+' → '+r.to+' · '+(r.family==='STRUCTURAL'?'Quan hệ cấu trúc':'Cơ chế có điều kiện')));box.append(chain);
   box.append(el('h4','Điều chưa biết'));const unknown=el('ul');for(const u of card.unknowns)unknown.append(el('li',u));box.append(unknown);
   const details=el('details');details.append(el('summary','Narrative, điều kiện và bằng chứng'));
   details.append(el('p',card.narrative.thesis),el('p','Phạm vi: '+card.narrative.scope+' · '+card.narrative.horizon));
   for(const [label,values] of [['Giả định',card.narrative.assumptions],['Theo dõi tiếp',card.narrative.reconsider_when]]){details.append(el('h4',label));for(const v of values)details.append(el('p',v));}
   for(const r of card.path){details.append(el('h4',r.from+' → '+r.to),el('p',r.scope));for(const c of r.conditions)details.append(el('p','Điều kiện: '+c));for(const e of r.evidence)details.append(el('blockquote',e.quote));}
   for(const source of card.sources)details.append(profileLink(source),el('br'));box.append(details,el('p','Sự kiện: '+date(card.occurred_at)+' · Có trong hệ thống: '+date(card.available_at),'meta'),el('p','Chưa xác định tác động giá cổ phiếu. Không tự duyệt quan hệ vào graph chung. Thông báo thật tắt.','meta'));root.append(box);
  }
 }
}
const $=id=>document.getElementById(id);let token='',epoch=0,busy=false;
const el=(tag,text,cls)=>{const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;};
const date=x=>x?new Date(x).toLocaleString('vi-VN'):'Không rõ';
async function api(path){const r=await fetch('/api/v0/news'+path,{headers:{Authorization:'Bearer '+token},cache:'no-store'});if(!r.ok)throw new Error(r.status===401?'Mã truy cập không hợp lệ hoặc hết hạn.':'Không tải được tin; thử lại sau.');return r.json();}
async function refresh(){if(!token||busy||document.hidden)return;busy=true;renderArticles(null);$('extraction-list').replaceChildren();$('impact-case-list').replaceChildren();$('profile-list').replaceChildren();$('rss-profile-list').replaceChildren();$('reviewed-role-list').replaceChildren();$('reviewed-operation-list').replaceChildren();$('reviewed-list').replaceChildren(el('p','Đang kiểm tra lại hiệu lực sự kiện…','meta'));const gen=epoch;try{const [feed,sources,clusters,reviewed,extractions,cases,profiles,profileNews,roleNews,operationNews,articleNews]=await Promise.all([api('?limit=200'+($('source').value?'&source='+encodeURIComponent($('source').value):'')),api('/sources'),api('/clusters'),api('/reviewed?limit=200').catch(()=>null),api('/extractions').catch(()=>null),api('/impact-cases').catch(()=>null),api('/profiles').catch(()=>null),api('/profile-rss').catch(()=>null),api('/reviewed-roles').catch(()=>null),api('/reviewed-operations').catch(()=>null),api('/profile-articles').catch(()=>null)]);if(gen!==epoch)return;$('connect').hidden=true;$('workspace').hidden=false;$('notice').textContent='Đã cập nhật lúc '+new Date().toLocaleTimeString('vi-VN');$('news-list').replaceChildren();renderClusters(clusters);renderReviewed(reviewed);renderExtractions(extractions);renderImpactCases(cases);renderProfiles(profiles);renderProfileNews(profileNews);renderRoleNews(roleNews);renderRoleNews(operationNews,true);renderArticles(articleNews);$('count').textContent=feed.items.length+' tin mới nhất từ các nguồn đã chọn';for(const item of feed.items){const card=el('article','', 'news-card');card.append(el('span',item.source_name+' · '+item.category,'meta'),el('h2',item.title));if(item.summary)card.append(el('p',item.summary));card.append(el('p','Mốc nguồn: '+date(item.published_at)+' · Nhận: '+date(item.first_seen_at),'meta'));card.append(el('p','Chưa thẩm định tác động'+(item.ticker_mentions.length?' · Đề cập: '+item.ticker_mentions.join(', '):'')+(item.version>1?' · Bản sửa '+item.version:''),'meta'));const a=el('a','Đọc tại nguồn ↗');try{const u=new URL(item.url);if(['https:','http:'].includes(u.protocol)){a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';card.append(a);}}catch{}$('news-list').append(card);}if(!feed.items.length)$('news-list').append(el('p','Chưa có tin từ nguồn đã chọn. Kiểm tra tình trạng nguồn bên dưới.'));$('sources').replaceChildren();const selected=$('source').value;$('source').replaceChildren(new Option('Tất cả nguồn',''));for(const s of sources.items){$('source').append(new Option(s.name,s.id));$('sources').append(el('p',s.name+' · '+(!s.enabled?'Chưa bật':s.stale?'Dữ liệu cũ / chưa nhận được':s.status)+' · Lần thành công: '+date(s.last_success)+' · Chu kỳ '+s.interval_seconds+' giây','source-line'+(s.stale?' stale':'')));}$('source').value=selected;}catch(e){if(gen===epoch){$('notice').textContent=e.message;renderArticles(null);renderReviewed(null);renderExtractions(null);renderImpactCases(null);renderProfiles(null);renderProfileNews(null);renderRoleNews(null);renderRoleNews(null,true);}}finally{busy=false;if(gen!==epoch&&token&&!document.hidden)refresh();}}
$('connect').addEventListener('submit',e=>{e.preventDefault();epoch++;clearReading();token=$('token').value.trim();$('token').value='';refresh();});
$('reading-preferences').addEventListener('toggle',()=>{if($('reading-preferences').open&&token)loadReading();});
$('reading-form').addEventListener('submit',async e=>{e.preventDefault();if(readingVersion===null||!token)return;const gen=epoch;const selected=id=>[...$(id).querySelectorAll('input:checked')].map(x=>x.value);$('save-reading').disabled=true;try{const response=await fetch('/api/v0/news/article-preferences',{method:'PUT',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json','Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({expected_version:readingVersion,tickers:selected('reading-tickers'),narratives:selected('reading-narratives'),following_only:$('following-only').checked,include_archive:$('include-archive').checked})});if(gen!==epoch||!token)return;if(!response.ok){$('reading-status').textContent=response.status===409?'Lựa chọn đã đổi ở phiên khác. Đóng rồi mở lại để tải trước khi lưu.':'Không lưu được; lựa chọn cũ vẫn giữ nguyên.';return;}const data=await response.json();readingVersion=data.version;$('reading-status').textContent='Đã lưu theo tài khoản.';refresh();}catch{if(gen===epoch)$('reading-status').textContent='Không kết nối được; kiểm tra lại lựa chọn đã lưu trước khi thử lại.';}finally{if(gen===epoch)$('save-reading').disabled=false;}});
$('article-ticker').addEventListener('change',()=>renderArticles(articleResult));
$('article-narrative').addEventListener('change',()=>renderArticles(articleResult));
$('logout').addEventListener('click',()=>{clearReading();renderArticles(null);epoch++;token='';$('token').value='';$('workspace').hidden=true;$('connect').hidden=false;$('news-list').replaceChildren();$('reviewed-list').replaceChildren();$('extraction-list').replaceChildren();$('impact-case-list').replaceChildren();$('profile-list').replaceChildren();$('rss-profile-list').replaceChildren();$('reviewed-role-list').replaceChildren();$('reviewed-operation-list').replaceChildren();$('sources').replaceChildren();$('cluster-list').replaceChildren();$('source').replaceChildren(new Option('Tất cả nguồn',''));$('notice').textContent='Đã xóa mã truy cập và nội dung khỏi trang.';});
$('refresh').addEventListener('click',refresh);$('source').addEventListener('change',()=>{epoch++;refresh();});setInterval(()=>{if(!document.hidden)refresh();},60000);

function renderClusters(result){const root=$('cluster-list');root.replaceChildren();root.append(el('p',result.cluster_count+' nhóm ứng viên từ '+result.source_items+' mục tin'+(result.truncated?' · Chỉ xét 500 mục gần nhất':''),'meta'));for(const group of result.items){const box=el('article','','news-card');box.append(el('h2',group.title),el('p',group.member_count+' mục · '+group.unique_articles+' URL bài · '+group.publisher_group_count+' nhóm nhà xuất bản đã nhận diện','meta'));if(group.potential_conflicts.length)box.append(el('p','Cần đối chiếu: khác biệt số liệu hoặc hướng biến động; chưa khẳng định mâu thuẫn.','stale'));box.append(el('p','Chưa chuyển sang Impact Engine: cần kiểm duyệt nội dung, kỳ so sánh, mức phơi nhiễm và đường quan hệ.','meta'));const details=el('details');details.append(el('summary','Xem nguồn và phiên bản'));for(const member of group.members){const p=el('p');const a=el('a',member.publisher_group+' · '+member.title);try{const u=new URL(member.url);if(['https:','http:'].includes(u.protocol)){a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';}}catch{}p.append(a,el('span',' · v'+member.version+' · Nhận '+date(member.received_at),'meta'));details.append(p);}box.append(details);root.append(box);}}

fetch("/api/v0/client-capabilities").then(r=>r.json()).then(c=>{if(!c.read_only)$("review-link").hidden=false;}).catch(()=>{});

function renderReviewed(result){
 const root=$('reviewed-list');root.replaceChildren();
 if(!result){root.append(el('p','Không kiểm tra được hiệu lực. Đã ẩn sự kiện đã duyệt; hãy tải lại.','stale'));return;}
 if(!result.enabled){root.append(el('p','Feed sự kiện đã duyệt chưa bật.','meta'));return;}
 root.append(el('p','Kiểm tra lúc '+date(result.as_of)+(result.truncated?' · Chỉ xét 200 sự kiện gần nhất':'')+' · '+result.withheld_count+' sự kiện không còn đủ điều kiện hiển thị.','meta'));
 if(result.exposure_truncated)root.append(el('p','Tỷ trọng nền chỉ xét 500 bản thẩm định gần nhất.','meta'));
 if(!result.items.length)root.append(el('p','Chưa có sự kiện news đã duyệt còn hợp lệ.','meta'));
 for(const item of result.items){
  const card=el('article','','news-card');
  card.append(el('h3',item.headline),el('p',item.excerpt),el('p','Bản '+item.version+(item.version>1?' · Đã sửa':'')+' · Mốc nguồn '+date(item.published_at)+' · Nhận '+date(item.captured_at)+' · Nhập hệ thống '+date(item.available_at),'meta'));
  card.append(el('p','Đã kiểm duyệt trích đoạn · Tác động: chưa xác định · Không xác nhận nhân quả','meta'));
  card.append(el('p','Người lập: '+(item.author_kind==='AI_SIMULATED'?'Agent AI':'Người dùng tự khai')+' · Người duyệt: '+(item.reviewer_kind==='AI_SIMULATED'?'Agent AI':'Người dùng tự khai'),'meta'));
  const m=item.measurement;
  if(m&&m.new_value!==null)card.append(el('p',(m.metric_id||'Chỉ tiêu')+': '+m.new_value+' '+(m.unit||'')+' · Kỳ '+(m.period||'không rõ')+(m.old_value!==null?' · So với '+m.old_value+' ở kỳ '+item.comparison_period:'')));
  for(const share of item.baseline_shares||[]){
   const box=el('details');box.append(el('summary',share.segment+' · tỷ trọng doanh thu nền '+share.percent+'%'));
   box.append(el('p','Không phải phần doanh thu bị ảnh hưởng bởi tin. Materiality và nhân quả chưa xác định.'));
   box.append(el('p',share.numerator.current.value+' / '+share.denominator.current.value+' '+share.denominator.unit+' · '+share.numerator.current.start+' → '+share.numerator.current.end));
   box.append(el('p','Duyệt lúc '+date(share.reviewed_at)+' · '+share.reviewer_kind,'meta'));
   for(const operand of [share.numerator,share.denominator]){const a=el('a','Hồ sơ SEC ↗');try{const u=new URL(operand.filing_url);if(u.protocol==='https:'){a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';box.append(a);}}catch{}}
   card.append(box);
  }
  const link=el('a','Đối chiếu tại nguồn ↗');try{const u=new URL(item.source_url);if(['https:','http:'].includes(u.protocol)){link.href=u.href;link.target='_blank';link.rel='noopener noreferrer';card.append(link);}}catch{}
  root.append(card);
 }
}
document.addEventListener('visibilitychange',()=>{epoch++;renderArticles(null);$('reviewed-list').replaceChildren();$('extraction-list').replaceChildren();$('impact-case-list').replaceChildren();$('profile-list').replaceChildren();$('rss-profile-list').replaceChildren();$('reviewed-role-list').replaceChildren();$('reviewed-operation-list').replaceChildren();if(!document.hidden)refresh();});


function renderExtractions(result){
 const root=$('extraction-list');root.replaceChildren();
 if(!result){root.append(el('p','Không kiểm tra được nguồn. Đã ẩn các bản trích.','stale'));return;}
 if(!result.enabled||!result.items.length){root.append(el('p','Chưa có bản trích hiện còn đủ bằng chứng nguồn.','meta'));return;}
 for(const item of result.items){
  const f=item.fields;const card=el('article','','news-card');
  card.append(el('h3','Bản trích chưa xác minh · '+f.metric.quote+' · '+f.basis.quote),el('p',f.current.quote+': '+item.currency_symbol+f.value.quote+' '+f.scale.quote+' · '+f.prior.quote+': '+item.currency_symbol+f.prior_value.quote+' '+f.scale.quote));
  card.append(el('p','Tiền tệ, kỳ kế toán chuẩn hóa và phạm vi: chưa xác minh. Không phải kết luận tác động.','stale'),el('p','Nguồn ngữ cảnh: '+item.source_relation+' · Tải lúc '+date(item.available_at),'meta'));
  const a=el('a','Đối chiếu tại nguồn ↗');try{const u=new URL(item.source_url);if(u.protocol==='https:'){a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';card.append(a);}}catch{}
  root.append(card);
 }
 if(result.truncated)root.append(el('p','Kết quả có giới hạn; không đại diện toàn bộ dữ liệu.','meta'));
}


function renderImpactCases(result){
 const root=$('impact-case-list');root.replaceChildren();
 if(!result){root.append(el('p','Không kiểm tra được ca tác động; đã ẩn dữ liệu.','stale'));return;}
 if(!result.items.length){root.append(el('p','Chưa có ca còn đủ bằng chứng tại thời điểm đọc.','meta'));return;}
 for(const c of result.items){const box=el('article','','news-card');
 box.append(el('h3',c.title),el('p',c.event_period.start+' → '+c.event_period.end+' · GAAP · USD'),el('p','Chi phí đã ghi nhận: '+Number(c.recognized_charge_usd).toLocaleString('vi-VN')+' USD'),el('p','Quy mô tương đương '+c.charge_over_revenue_percent+'% doanh thu. Đây không phải tỷ lệ doanh thu bị ảnh hưởng.'),el('p','Giảm biên gộp có điều kiện: '+c.conditional_margin_drag_pp+' điểm %. Giữ doanh thu và các chi phí khác cố định.'));
 box.append(el('p','AI đối chiếu · Nhân quả: lời giải thích của doanh nghiệp · Tác động giá và dòng tiền: chưa xác định.','stale'));
 const d=el('details');d.append(el('summary','Xem chuỗi, phép tính và giới hạn'));for(const step of c.chain)d.append(el('p',step.from+' → '+step.to+' · '+step.status));d.append(el('pre',JSON.stringify({operands:c.operands,comparison:c.comparison,limits:c.scope_limitations},null,2)));d.lastChild.style.whiteSpace='pre-wrap';box.append(d);
 for(const src of c.sources){const a=el('a','Nguồn '+src.role+' ↗');try{const u=new URL(src.url);if(u.protocol==='https:'){a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';box.append(a,el('br'));}}catch{}}
 root.append(box);}
}
