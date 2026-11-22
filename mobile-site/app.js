"use strict";
fetch("./connection.json", {cache:"no-store"}).then(r=>{if(!r.ok)throw new Error();return r.json();}).then(data=>{
 const u=new URL(data.origin);
 if(u.protocol!=="https:"||!/^[-a-z0-9]+\.trycloudflare\.com$/.test(u.hostname)||u.username||u.password||u.port||u.pathname!=="/"||u.search||u.hash)throw new Error();
 for(const id of ["news","map"]){const a=document.getElementById(id);a.href=u.origin+"/"+id;a.rel="noreferrer noopener";a.removeAttribute("aria-disabled");}
 document.getElementById("status").textContent="Kết nối được bảo vệ bằng email và mã truy cập. Trạng thái server sẽ được kiểm tra khi bạn mở ứng dụng.";
}).catch(()=>{document.getElementById("status").textContent="Chưa tải được địa chỉ kết nối. Hãy tải lại trang.";});
