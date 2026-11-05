# Belgesel mekanikleri

Sahibinin kuralı: **her belgesel farklı bir konseptte ve farklı bir görsel mekanikte olmalı.** Sabit formatlar yok. Her belgeselde
yeni bir mekanik tasarlanır, bu klasöre `<ad>.py` olarak eklenir ve `script.json` içinde `"mechanic": "<ad>"` ile kullanılır.
Bir kez kullanılan mekanik (`youtube/published.md` içindeki `Mekanik:` satırları) bir daha kullanılmaz.

**Mekanik konudan doğar:** video neyle ilgiliyse mekanik ve tasarım da onunla ilgili olmalı. Sahibinin beğendiği örnek: hız belgeselinde
araba hız göstergesi (`speed_dial`). Genel bir kalıbı konuya giydirme; önce "bu konuyu en iyi hangi gösterge/nesne/grafik anlatır?" diye sor.

İlham: dünyanın en çok izlenen belgesel ve hayvan kanalları (BBC Earth, National Geographic, Kurzgesagt, MetaBallStudios,
RealLifeLore, Animalogic, Casual Geographic, TierZoo, Zoo / "who would win" kanalları, quiz kanalları). **Birebir kopyalama yok:**
fikri al, kendi düzenini, renklerini, animasyonunu ve anlatım akışını kur.

## Nasıl çalışır

`youtube/tools/doc_render.py`, `script.json`'da `mechanic` varsa `youtube/mechanics/<ad>.py` dosyasındaki `Mechanic` sınıfını yükler:

```python
import doc_render as R            # W, H, CARD, SUB_CX, ease, font, F_ANTON, F_UI, F_IT, F_ROBOTO, tr_upper, tr_title

class Mechanic:
    subtitles = True              # False: alt yazıyı mekanik kendisi çizer (ya da hiç çizmez)

    def __init__(self, scene):    # scene.spec (script.json), scene.blocks (zaman çizelgesi), scene.photos (photos.json)
        self.s = scene

    def background(self, d, t, b):          # İSTEĞE BAĞLI: 1920x1080 PIL RGB görüntüsü ya da (H, W, 3) numpy dizisi
        ...

    def draw(self, img, t, b, lt, default):  # her kare: img (PIL, değiştir), t saniye, b o anki blok, lt bloğun içindeki saniye
        default()                            # standart katman (sayaç, kartlar, başlıklar); istersen çağırma
        ...
```

- **Blok** (`b`): `kind` (`cold`, `travel`, `rank`, `intro`, `zone`, `creature`, `landmark`, `outro`, `end` ya da senin
  segment türün), `t0`, `dur`, `i` (segment no), `seg` (segmentin kendisi, ekstra alanlarınla birlikte), `voice`, `subs`.
  `self.s.blocks` tüm bloklardır: önceki/sonraki canlılara bakarak birikmeli şeyler (tablo, harita, ağ, skor) çizebilirsin.
- **Hazır yardımcılar** (`self.s`): `photo(key)`, `kenburns(key, x, n)` (kart boyutunda hareketli foto), `card_photo_frame(keys, lt, dur)`,
  `place_card(img, ph, alpha, overlays)`, `card(img, b, lt)`, `plate(seg)`, `credit(meta)`, `big_title(key, title, sub, size)`,
  `subtitle(text)`, `paste(img, over, xy, alpha)`, `text_img(key, fn)` (pahalı çizimleri önbelleğe al: anahtar değişmedikçe tekrar çizilmez).
- **Yerleşim:** `journey.card` = `[x, y, w, h]` foto kartının yeri ve boyutu (16:9 tut), `journey.sub_cx` = alt yazının yatay merkezi.
  `"meter": false` ise sol sayaç yok.
- **Segment alanları:** Segmentlere istediğin ekstra alanı ekle (`tier`, `score`, `lat`/`lon`, `year`, `speed`, `clue`…); mekanik
  okur. `"hold": <saniye>` sesten önce sessiz bekleme ekler (bilmece, açılış, sonuç ilanı için). Yeni segment türleri kullanabilirsin;
  `default()` onları çizmez, sen çizersin. Bölüm listesine sadece `zone` ve `creature` girer.
- **Telif:** Sadece `photos/` içindeki telifsiz fotoğraflar ve kodla çizilen şekiller. İnternetten başka görsel, harita ya da font indirme.
- **Hız:** Her kare 1/30 saniyede değil ama makul sürede çizilmeli (30 dk = 54.000 kare, 16 paralel iş). Statik katmanları
  `text_img` ile önbelleğe al; her karede büyük görüntü üretme.
- **Kontrol:** `python youtube/tools/doc_render.py youtube/docs/<klasör> --preview` → `out/preview.jpg` (12 an, ses olmadan da çalışır).
  Belirli anlar için `--stills 120.5,300`. Read ile aç ve gözle kontrol et: yazılar taşmıyor mu, hayvan görünüyor mu, mekanik anlaşılıyor mu?

Örnek: `tier_list.py` (her canlıya S–D notu verilir, portresi sağdaki tabloya uçar).

## Fikir havuzu (kullanılanları published.md'den kontrol et; yenilerini de üret)

- **Turnuva braketi:** 16 hayvan ikişer ikişer karşılaşır; güç, hız, zehir, savunma çubukları kıyaslanır, kazanan üst tura çıkar, ağaç dolar.
- **Dünya haritası turu:** Kodla çizilmiş nokta-ızgara dünya haritası; her canlının `lat`/`lon` noktasına iğne düşer, rota kıtadan kıtaya çizilir.
- **Ölçek dizisi:** Hayvanlar bir insan silüetinin yanında boy sırasına dizilir; kamera sağa kayar, cetvel ölçeği değişir.
- **Gece-gündüz saati:** 24 saatlik dairesel saat; her canlı en aktif olduğu saatte belirir (gece avcıları, şafak kuşları), gökyüzü rengi saate göre değişir.
- **Besin ağı:** Ekranda düğümler; her yeni canlı eklendikçe "kimi yer, kim tarafından yenir" okları bağlanır, ağ büyür.
- **Evrim zaman tüneli:** Yatay kayan zaman çizgisi (milyon yıl); canlılar ortaya çıktıkları döneme yerleşir ("yaşayan fosiller").
- **Bilmece:** Bulanık/kırpılmış foto ve 3 ipucu, geri sayım, sonra büyük açılış ("Bu hayvan hangisi?").
- **Kart düellosu:** Koleksiyon kartı tarzı istatistik kartları; her canlı bir öncekini bir istatistikte geçer, en iyiler podyuma.
- **Yarış pisti:** Hız/göç mesafesi/dalış derinliği için yatay yarış; çubuklar canlı canlı uzar, sıralama değişir.
- **Radar grafiği:** Her canlının 5 özelliği (güç, hız, zekâ, zehir, kamuflaj) örümcek ağı grafiğinde çizilir ve bir öncekiyle üst üste kıyaslanır.
- **Göç takvimi:** 12 aylık halka takvim; her ay bir canlının göçü/üreme zamanı, ok haritada ilerler.
- **Gerçek mi efsane mi:** Yaygın inanış ekranda, sonra "DOĞRU" / "YANLIŞ" damgası ve kanıt.
- **Rekor podyumu:** Her kategori için bronz-gümüş-altın podyum; madalyalar canlılara yapışır, sonda madalya tablosu.
- **Laboratuvar dosyası:** Gizli dosya / tür kimlik kartı estetiği; parmak izi gibi tarama animasyonu, "sınıflandırma" bilgileri satır satır yazılır.
