# Terra Wild Nature — günlük içerik üretimi

Bu depo @terrawildnature Instagram hesabı için otomatik gönderi üretir.
- **Sen (Claude, bulut görevi):** Her gün günün 3 gönderisini hazırlayıp `queue/` klasörüne eklersin.
- **GitHub Actions (`.github/workflows/publish.yml`):** 09:00, 18:00 ve 22:00'de (Türkiye) `queue/` içindeki en eski gönderiyi paylaşır.
- **GitHub Actions (`.github/workflows/publish-reel.yml`):** Pazartesi, Çarşamba, Cuma, Pazar 20:00'de `queue_reels/` içindeki en eski Reels tarifinden videoyu üretip paylaşır (bkz. bölüm 6).

Sen Instagram'a hiçbir şey göndermezsin. Görevin yalnızca gönderi hazırlamak, commit'lemek ve push'lamak.

## Her çalıştırmada

0. Kurulum: `python3 -m pip install -q --break-system-packages --ignore-installed pillow numpy` (sistemdeki PIL bozuk, düz `pip install` yetmiyor). Commons istekleri arasında birkaç saniye bekle; 429 alırsan araç kendisi bekleyip tekrar dener.
1. `queue/` içindeki gönderi klasörlerini say. **6 veya daha fazlaysa** hiçbir şey üretme, "kuyruk dolu" yazıp bitir.
2. Değilse **3 yeni gönderi** hazırla (aşağıdaki adımlar).
3. Her gönderiyi `python tools/render.py queue/<klasör>` ile üret. `OVERFLOW` hatası verirse metni kısaltıp tekrar dene.
4. Üretilen `a.jpg` ve `b.jpg` dosyalarını **Read aracıyla açıp gözle kontrol et:** Fotoğrafta hayvan net görünmeli, kesilmemeli ve yazılarla çakışmamalı. Sorun varsa kırpmayı (`cx`, `cy`, `zoom`) ya da fotoğrafı değiştir.
5. Kaynak fotoğrafları (`photo_*.jpg`) sil. Depoda sadece `post.json`, `a.jpg` ve `b.jpg` kalmalı.
6. Canlıların adlarını `data/used.txt` sonuna ekle.
7. `git add -A && git commit -m "Yeni gönderiler: <adlar>" && git push` (çakışma olursa `git pull --rebase` sonra tekrar push).

## 0. Önce performans raporunu oku

`data/insights.md` her sabah 05:05'te gerçek Instagram istatistiklerinden yeniden üretilir. Canlı seçmeden ve başlık yazmadan **önce** oku ve şöyle kullan:
- Rapordaki **"güçlü — daha sık kullan"** grup ve kanca tarzlarına öncelik ver. **"zayıf"** olanları daha seyrek kullan (tamamen bırakma).
- Günün 3 gönderisinden **2'si** güçlü/ortalama bir grup + kanca tarzıyla, **1'i** keşif amaçlı olsun: "veri yetersiz" ya da hiç denenmemiş bir grup veya kanca tarzı. Reels için de aynı mantık: güçlü tarzlara ağırlık ver, arada farklısını dene.
- "En iyi 5" listesindeki başlıkların neden tuttuğunu düşün (sayı mı, şaşkınlık mı, tehlike mi) ve benzer etkide **yeni** başlıklar yaz. Aynı başlığı kopyalama.
- Rapor yoksa ya da veri azsa grupları ve kanca tarzlarını dengeli dağıt.
- Rapor **sadece** canlı seçimini, canlı grubunu, kanca tarzını ve başlık/metin ifadesini etkiler. Tasarım şablonu (`assets/`, `tools/render.py`, `tools/reel.py`: yazı tipleri, renkler, yerleşim, rozet, kapak düzeni) **asla** değişmez, rapor ne derse desin.
- Son mesajında, rapordan ne öğrendiğini ve seçimlerine nasıl yansıttığını tek cümleyle yaz.

Her `post.json` ve `reel.json` dosyasına bu iki alanı **mutlaka** ekle (analiz bunlarla yapılıyor):
- `"group"`: `memeli` | `kuş` | `sürüngen` | `amfibi` | `balık` | `deniz omurgasızı` | `böcek/örümcek` | `diğer`
- `"hook_style"`: `sayı` (rakamlı iddia: "350 KİLO") | `süperlatif` ("dünyanın en...") | `tuhaf yetenek` (beklenmedik davranış/yetenek) | `tehlike` (zehir, ölümcül, saldırı) | `gizem` (az bilinen, yeni keşif, kayıp tür) | `benzetme` ("X gibi ama Y") | `tuhaf görünüm` (garip vücut, organ)

## 1. Canlı seçimi

- `data/used.txt` içindeki **hiçbir canlıyı seçme.** Emin olmak için canlının Türkçe, İngilizce ve bilimsel adını `data/instagram_posts.txt` içinde de ara (grep, büyük/küçük harf duyarsız). Bulursan seçme. Aynı canlının farklı bir türünü de seçme (ör. "kasuar" varsa "kuzey kasuarı" da olmaz).
- Hesabın tarzı: **vahşi doğadan, az bilinen, "bu gerçek mi?" dedirten** canlılar. Fotoğrafta çarpıcı duranları tercih et: memeliler, kuşlar, sürüngenler, balıklar, büyük böcekler, deniz canlıları.
- Mikroskobik canlılar, sadece mikroskop görüntüsü olanlar ve çok bilinen hayvanlar (aslan, kedi, köpek vb.) olmaz.
- Aynı gün içinde çeşitlilik olsun: 3 gönderinin üçü de aynı gruptan (ör. üç kuş) olmasın.
- Önce fotoğraf durumunu kontrol et (adım 2). Uygun fotoğrafı yoksa başka canlı seç.

## 2. Fotoğraflar (telif kuralları — çok önemli)

`python tools/commons.py search "<bilimsel ad>"` ile Wikimedia Commons'ta ara. Liste önce `[PD]` (kamu malı) olanları gösterir.

- **Öncelik kamu malı (`[PD]`, CC0, PD-USGov, NOAA, USFWS, NPS).** Bunlarda kaynak yazma zorunluluğu yok.
- Kamu malı yoksa **CC BY** veya **CC BY-SA** kullanılabilir. Bu durumda açıklamaya kaynak satırı ZORUNLU (aşağıda).
- **ASLA kullanma:** NC (ticari olmayan), ND (türetilemez), "fair use", lisansı belirsiz olan, filigranlı, müze/hayvanat bahçesi tabelası görünen, ölü/doldurulmuş hayvan, çizim/illüstrasyon.
- En az 1600 px genişlik. Hayvan net ve odakta olmalı.
- 3 fotoğraf seç: `cover` (kapak, en çarpıcı), `top` (bilgi sayfası üstü), `inner` (küçük kutu, yakın plan). Mümkünse 3 farklı fotoğraf olsun. Yeterli fotoğraf yoksa aynı fotoğraf farklı kırpmayla kullanılabilir.
- İndir: `python tools/commons.py download "File:..." queue/<klasör>/photo_cover.jpg`. Çıktıdaki lisans ve yazar bilgisini `post.json` içindeki `credits` alanına kaydet.
- İndirdiğin her fotoğrafı Read ile aç ve doğru canlı olduğunu kontrol et. Commons aramaları bazen alakasız sonuç döndürür.

## 3. Bilgiler (doğruluk — çok önemli)

- Her iddiayı güvenilir kaynaktan doğrula: Wikipedia (İngilizce), IUCN, Britannica, üniversite veya müze sayfaları. Emin olmadığın sayıyı yazma.
- Doğrulama ZORUNLU: Her canlı için en az İngilizce Wikipedia sayfasını oku (WebFetch aracıyla `https://en.wikipedia.org/wiki/<Bilimsel_ad>`, olmazsa `curl`). Kapak başlığındaki ve kartlardaki her sayı ve iddia o sayfada (veya başka güvenilir kaynakta) geçmeli. Hiçbir kaynağa erişemiyorsan o gün gönderi üretme ve son mesajında bunu açıkça yaz.
- Abartma: "mermi hızında", "en ölümcül" gibi ifadeleri sadece kaynak öyle diyorsa kullan.
- Kapak başlığı, hayvanın en şaşırtıcı ve doğrulanmış tek özelliği olmalı.

## 4. post.json formatı

Klasör adı: `queue/<YYYYMMDD>-<n>_<ad>` (ör. `queue/20261024-1_babirusa`). Burada n=1,2,3, ad küçük harf ve Türkçe karaktersiz. Tarih, gönderinin hazırlandığı gün.

```json
{
  "name": "kasuar",
  "title": [
    [["BU KUŞUN AYAĞINDA", "W"]],
    [["12 CM'LİK", "W"], ["HANÇER", "R"]],
    [["VAR", "R"]]
  ],
  "card_title": "GÜNEY KASUARI",
  "card_top": ["İç parmağında 12 cm'lik", "hançer gibi bir pençe var."],
  "card_bottom": ["Tehlikede tek tekmeyle ciddi", "yaralar açabilir. Dünyanın en", "tehlikeli kuşu sayılır."],
  "right": ["Avustralya ve Yeni Gine'nin", "yağmur ormanlarında yaşar.", "Uçamaz ama saatte 50 km", "hızla koşar ve iyi yüzer.", "Yavrulara babaları bakar."],
  "loc": "Avustralya, Yeni Gine",
  "photos": {
    "cover": {"file": "photo_cover.jpg", "cx": 0.55, "cy": 0.5, "zoom": 1.3},
    "top":   {"file": "photo_top.jpg",   "cx": 0.55, "cy": 0.5, "zoom": 1.3},
    "inner": {"file": "photo_inner.jpg", "cx": 0.44, "cy": 0.42, "zoom": 2.2}
  },
  "credits": [
    {"use": "cover", "title": "File:...", "author": "...", "license": "CC BY-SA 4.0", "public_domain": false}
  ],
  "caption": "..."
}
```

Kurallar:
- **title:** Tam 3 satır, büyük harf (Türkçe İ/I'ya dikkat). Her satır `[metin, renk]` parçalarından oluşur. Renk `W` (beyaz) veya `R` (kırmızı). Kalıp: 1. satır beyaz giriş ("BU KUŞUN", "BU HAYVANIN"...), 2. satırda vurucu kısım kırmızıya döner, 3. satır kırmızı ve kısa. Satır başına en fazla yaklaşık 18-20 karakter.
- **card_title:** Canlının Türkçe adı, büyük harf, en fazla yaklaşık 24 karakter.
- **card_top:** Tam 2 satır. **card_bottom:** Tam 3 satır. Satır başına en fazla yaklaşık 28 karakter.
- **right:** Tam 5 satır, satır başına en fazla yaklaşık 29 karakter. Yaşam alanı ve ek ilginç bilgiler.
- **loc:** Kısa coğrafi bölge (ör. "Amazon", "Doğu Afrika", "Hint-Pasifik").
- **cx/cy:** Hayvanın fotoğraftaki merkezi (0-1). **zoom:** 1 = olabildiğince geniş. Kapakta alt %40 siyaha kararır, bu yüzden hayvanın başı/gövdesi üst yarıda kalmalı.
- Cümleleri satırlara doğal yerlerden böl.

## 5. Açıklama (caption) stili

Hesabın kendi tarzı: tek uzun cümle + 2 emoji + boş satır + 3 etiket. Örnek:

```
Avustralya'nın sevimli kazıcısı çıplak burunlu vombat, bağırsaklarının özel yapısı sayesinde küp şeklinde dışkı üretip bunlarla bölgesini işaretliyor. 🧱🐾

#terrawildnature #ilginçbilgiler #vombat
```

- Üçüncü etiket canlının Türkçe adı (boşluksuz, küçük harf).
- **Herhangi bir fotoğraf kamu malı DEĞİLSE**, etiketlerden sonra boş satır bırakıp kaynak satırı ekle:
  `📷 <Yazar> (<Lisans>), <Yazar> (<Lisans>) / Wikimedia Commons`
  Aynı yazar birden fazla fotoğrafta varsa bir kez yaz. Tamamı kamu malıysa kaynak satırı ekleme.

## 6. Reels (Pazartesi, Çarşamba, Cuma, Pazar 20:00)

Gönderilerden sonra `queue_reels/` klasörüne bak. **2'den az Reels varsa 1 yeni Reels tarifi hazırla.** Videoyu sen üretmiyorsun; GitHub Actions paylaşımdan hemen önce `tools/reel.py` ile üretiyor. Sen tarifi (`reel.json`) ve kapağı (`cover.jpg`) hazırlarsın.

- **Canlı:** Aynı yasak listesi (`data/used.txt` + `data/instagram_posts.txt`). Bu çalıştırmada gönderiler için seçtiğin canlılardan da farklı olmalı. En az 7 iyi fotoğrafı olan canlı seç (mümkünse doğal ortamda çekilmiş). Telif kuralları gönderilerle aynı.
- **Klasör:** `queue_reels/<YYYYMMDD>_<ad>` (Türkçe karaktersiz, küçük harf).
- **Metin:** 8-9 cümle, toplam 85-100 kelime (yaklaşık 40 saniye). Her bilgi Wikipedia'dan doğrulanmış olmalı. 1. cümle kanca: en şaşırtıcı bilgi. **Son cümle her zaman aynen:** `Canlılar hakkında daha fazla bilgi alabilmek için bizi takip etmeyi unutmayın.` Belgesel anlatıcısı tonu; kısa, akıcı cümleler.
- **Sahneler:** Her cümle bir sahne, her sahnede farklı fotoğraf. Yatay fotoğraflarda `pan_left`/`pan_right` (kamera hayvanın üzerinde kayar), dikey fotoğraflarda `zoom_in`/`zoom_out`. `cx`, `cy` hayvanın (tercihen başının) konumu.
- **Müzik:** Ruh haline göre biri: `assets/music/Reawakening.mp3` (sakin, görkemli), `assets/music/Investigations.mp3` (gizemli), `assets/music/Ancient_Rite.ogg` (vahşi, enerjik). `"loudness": -27`.
- **Kapak:** Hayvanın net ve büyük göründüğü fotoğraf. Başlık 3-4 satır, satır başına en fazla ~12 karakter, büyük harf; ilk ve/veya son satır kırmızı (`R`), diğerleri beyaz (`W`). Kısa, çarpıcı bir kanca (ör. `350 KİLO / AMA İKİ / AYAK ÜSTÜNDE / DURABİLİYOR`).
- **Açıklama (`caption`):** Tek cümle + 2 emoji, boş satır, `#terrawildnature #<canlıadı>`, boş satır; kamu malı olmayan fotoğraf varsa `📷 <Yazar> (<Lisans>) / Wikimedia Commons`; son satır her zaman `🎵 Kevin MacLeod (CC BY)`.
- `credits` alanına her fotoğrafın yazarını ve lisansını yaz.
- **Kontrol:** `python tools/reel.py --preview queue_reels/<klasör>` ve `python tools/reel.py --cover queue_reels/<klasör>` çalıştır (fotoğrafları `photos` listesinden kendisi indirir). `preview.jpg` ve `cover.jpg` dosyalarını Read ile aç: hayvan her karede görünmeli, başı kesilmemeli, kapak başlığı okunaklı ve ortada olmalı. Sorun varsa düzelt ve tekrar üret.
- Sonra `p*.jpg` ve `preview.jpg` dosyalarını sil. Klasörde sadece `reel.json` ve `cover.jpg` kalmalı. `data/used.txt` sonuna `<ad> (Reels) | <bilimsel ad>` ekle.

Örnek: `queue_reels/20261023_takin/reel.json` (bu dosya paylaşılınca `posted_reels/` altına taşınır; orada da bakabilirsin).

## Asla yapma

- Instagram'a doğrudan paylaşım yapma. `tools/publish.py` dosyasını çalıştırma.
- `queue/` içinde var olan gönderileri silme veya değiştirme (sen bu çalıştırmada eklemediysen).
- `assets/`, `tools/` ve `.github/` dosyalarını değiştirme. Bir hata bulursan son mesajında açıkla.
