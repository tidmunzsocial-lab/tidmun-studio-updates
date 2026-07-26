# แผนที่โปรแกรมสำหรับคนและ AI ที่มาแก้ภายหลัง

> เอกสารนี้เป็น Developer Note ไม่แสดงในหน้าจอโปรแกรม  
> ก่อนเปลี่ยน logic ให้ค้นหาหัวข้อ `SECTION NOTE` ใน `snapgen_gui_v2.py`

## กฎสำคัญที่สุด

1. อย่าเดา business logic จากชื่อฟังก์ชันเพียงอย่างเดียว
2. แยก “ทำความสะอาดไฟล์” ออกจาก “เปลี่ยนพฤติกรรมโปรแกรม”
3. หากจะเปลี่ยน Bridge, GPT, Tailscale, Restore, Update หรือ Account ต้องอ่าน
   เอกสารเฉพาะส่วนนั้นและขอคำสั่งจากเจ้าของก่อน
4. ห้ามลบไฟล์เพราะเห็นว่า import น้อย ต้องตรวจการเรียกผ่าน bytecode,
   `globals()`, callback และ dynamic import ก่อน
5. ห้ามแตะ `export` หรือข้อมูลผู้ใช้ระหว่าง Update/Restore

## 1. การเริ่มโปรแกรม

ไฟล์หลักที่เปิดคือ `snapgen_gui_v2.py`

หน้าที่ช่วงต้นไฟล์:

- ตรวจและใช้ Python ของ `.venv312`
- จัดตำแหน่งโฟลเดอร์เก่าให้เข้ารูปแบบปัจจุบัน
- ตรวจ Bridge และเปิด Bridge เมื่อจำเป็น
- โหลดแกนโปรแกรมจาก `__pycache__/snapgen_core.cpython-312.pyc`
- ติดตั้ง patch/UI adapters เพิ่มจาก source ด้านล่าง

ไฟล์ `.pyc` เป็นส่วนสำคัญของโปรแกรม ไม่ใช่ cache ธรรมดาที่ลบได้

## 2. Bridge, GPT และ Tailscale

อ่านรายละเอียดทั้งหมดที่ `docs/BRIDGE_TEAM_ARCHITECTURE.md`

สรุป:

```text
แต่ละเครื่อง → SnapGen ของตัวเอง → Bridge ของตัวเอง → GPT บัญชีเดียวกัน
```

ทุกเครื่องใช้ Tailscale บัญชี/เครือข่ายเดียวกัน แต่ไม่มี Central Bridge

ค่าที่ต้องแยกให้ออก:

```text
SnapGen ติดต่อ Bridge       = 127.0.0.1
Bridge process เปิดบริการ   = 0.0.0.0
```

ห้ามเปลี่ยนสองค่านี้จากการคาดเดา

## 3. Restore — มีปุ่มเดียว

ใน Settings มีปุ่มชื่อ `Restore` เพียงปุ่มเดียว

หน้าที่:

1. ดึงรายการเวอร์ชันที่เผยแพร่ไว้ใน GitHub Releases
2. ให้ผู้ใช้เลือกเวอร์ชันที่ต้องการ
3. ดาวน์โหลด `tidmun-studio-patch.zip`
4. ตรวจ SHA-256 ของไฟล์ทุกตัวจาก manifest
5. เปลี่ยนเฉพาะไฟล์ตัวโปรแกรมที่อนุญาต
6. ปิดและเปิดโปรแกรมใหม่

Restore ใช้ได้ทั้งย้อนกลับรุ่นเก่าและติดตั้งรุ่นที่เลือก

Restore ไม่ใช่ Backup และต้องไม่แตะ:

- `export`
- รูปหรือวิดีโอของผู้ใช้
- GPT accounts/cookies
- Chrome profile
- การตั้งค่าหรือข้อมูล runtime ใน `snapgen_data`

ตำแหน่งสำคัญ:

- ปุ่มและหน้าต่างเลือกเวอร์ชัน: `run_restore()` ใน `snapgen_gui_v2.py`
- รายการ Release และการดาวน์โหลด: `snapgen_modules/snapgen_updater.py`
- การสร้าง Patch: `tools/build_update_patch.py`
- การเผยแพร่เวอร์ชัน: `tools/publish_update.ps1`

ห้ามสร้างปุ่ม Restore ตัวที่สอง และห้ามนำ Local Backup/ZIP Restore เก่ากลับมา

## 4. Update

Update ต่างจาก Restore ตรงที่ Update เลือกรุ่นล่าสุดให้อัตโนมัติหลังผู้ใช้กด
ตรวจอัปเดต ส่วน Restore ให้ผู้ใช้เลือกเวอร์ชันเอง

ทั้งสองระบบใช้ตัวดาวน์โหลดและตัวติดตั้งเดียวกัน จึงต้องรักษาการตรวจ manifest
และ SHA-256 ไว้เสมอ

## 5. Settings และปุ่มเครื่องมือ

ฟังก์ชัน `_add_settings_maintenance_buttons()` เป็นเจ้าของแถวปุ่มเครื่องมือ
ใน Settings และต้องตรวจปุ่มเดิมก่อนสร้าง เพื่อป้องกันปุ่มซ้ำ

ปุ่มสำคัญในแถวนี้:

- ตรวจและแก้บัค
- ตรวจอัปเดต
- Restore
- ล้าง export
- จับ Account
- อัปขึ้น GitHub เฉพาะเครื่อง Publisher

## 6. Export

`export` คือไฟล์งานของผู้ใช้ ไม่ใช่ไฟล์ตัวโปรแกรม

- Restore และ Update ห้ามลบหรือเขียนทับ
- ปุ่ม `ล้าง export` เป็นคำสั่งแยกและต้องถามยืนยัน
- ห้ามเลือก root drive หรือโฟลเดอร์โปรเจกต์เป็น Export path

## 7. หน้าฟีเจอร์

ไฟล์หลักของแต่ละหน้าอยู่ใน `snapgen_modules`:

- Image: `snapgen_page_image.py`
- Video: `snapgen_page_video.py`
- Reference: `snapgen_page_ref.py`
- Prop 3D: `snapgen_page_prop.py`
- Story/Face: `snapgen_page_story_face.py`
- Karaoke: `snapgen_page_karaoke.py`

โมดูลเหล่านี้บางตัวถูกติดตั้งผ่าน callback หรือ dynamic import ห้ามสรุปว่า
ไม่ได้ใช้จากการค้นหา import แบบธรรมดาเพียงอย่างเดียว

## 8. เครื่องมือ AI ภายนอก

- Slow motion: `ai_slow2x.py`
- Upscale: `ai_upscale.py`
- Hunyuan 3D: `hunyuan3d.py`

เครื่องมือและโมเดลที่ดาวน์โหลดต้องอยู่ใต้ `snapgen_data/tools` ไม่ควรคัดลอก
ไปไว้ใน `snapgen_modules`

## 9. Error log

ข้อผิดพลาดที่หลุดจาก callback หรือ background thread จะบันทึกที่:

```text
snapgen_data/logs/unhandled_errors.log
```

อย่ากลืน error สำคัญด้วย `except Exception: pass` หาก error นั้นทำให้งานของ
ผู้ใช้ไม่สำเร็จ ควรเขียน log หรือแสดงข้อความที่เข้าใจได้

## 10. ก่อนเผยแพร่เวอร์ชัน

ตรวจอย่างน้อย:

1. Python compile ผ่าน
2. `git diff --check` ผ่าน
3. Patch มี `manifest.json`
4. Patch ไม่มี `export`, cookies, accounts หรือข้อมูลใน `snapgen_data`
5. GitHub Release มี asset ชื่อ `tidmun-studio-patch.zip`
6. Restore เห็นเวอร์ชันใหม่จาก GitHub

## 11. ปุ่มต่อจากฉากก่อนในหน้า Image

ปุ่ม `📎 ต่อจากฉากก่อน` มีไว้เลือกภาพจากเหตุการณ์ก่อนหน้า เพื่อให้การสร้างภาพ
คนละรอบของ GPT ยังเป็นเหตุการณ์เดียวกัน ไม่ใช่ปุ่มเลือกไฟล์ล่าสุด และไม่ใช่
ปุ่มเลือกรูปตัวละครจากคลังอ้างอิง

- ต้องส่งภาพฉากก่อนหน้าไปกับการสร้างแบบ Manual ทุกครั้งจนกว่าผู้ใช้จะล้าง
- ต้องส่งภาพฉากก่อนหน้าก่อนรูปอ้างอิงอื่น เพื่อไม่ให้หลุดจากขีดจำกัด 10 รูป
- รูปตัวละครและสถานที่ที่จับคู่จากชื่อ Prompt ยังส่งร่วมกันได้
- ให้รักษาสถานที่ ตัวละคร เสื้อผ้า พร็อพ เวลา แสง และสภาพของเหตุการณ์เดิม
- เปลี่ยนสถานที่หรือรายละเอียดเดิมได้เมื่อ Prompt ใหม่สั่งอย่างชัดเจนเท่านั้น
- ห้ามนำปุ่ม `ล่าสุด` กลับมา เพราะการเดาไฟล์ล่าสุดอาจเลือกภาพผิดเหตุการณ์
