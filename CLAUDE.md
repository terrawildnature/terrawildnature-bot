# Terra Wild Nature — günlük içerik üretimi

Bu depo @terrawildnature Instagram hesabı için otomatik gönderi üretir.
- **Sen (Claude, bulut görevi):** Günde dört kez (05:30, 11:30, 17:30, 23:30) çalışır, kuyrukları **3 günlük yedekle** dolu tutarsın: günde **5 gönderi** (`queue/`) ve **3 Reels** (`queue_reels/`) paylaşılıyor.
- **GitHub Actions (`.github/workflows/publish.yml`):** 09:00, 12:00, 15:30, 18:00 ve 22:00'de (Türkiye) `queue/` içindeki en eski gönderiyi paylaşır.
- **GitHub Actions (`.github/workflows/publish-reel.yml`):** her gün 10:30, 13:30 ve 20:00'de `queue_reels/` içindeki en eski Reels tarifinden videoyu üretip paylaşır (bkz. bölüm 6). Aynı videolar YouTube Shorts olarak da yüklenir.

Sen Instagram'a hiçbir şey göndermezsin. Görevin yalnızca gönderi hazırlamak, commit'lemek ve push'lamak.

**YouTube belgeseli ayrı bir görevdir (haftada 2):** talimatları `youtube/ROUTINE.md`. Instagram görevinde `youtube/` klasörüne dokunma.

## Her çalıştırmada

0. Kurulum: `python3 -m pip install -q --break-system-packages --ignore-installed pillow numpy` (sistemdeki PIL bozuk, düz `pip install` yetmiyor). Commons istekleri arasında birkaç saniye bekle; 429 alırsan araç kendisi bekleyip tekrar dener.
1. `queue/` içindeki gönderi klasörlerini say. **15 veya daha fazlaysa** (3 günlük yedek) gönderi üretme ("gönderi kuyruğu dolu"), doğrudan Reels'e (bölüm 6) geç.
2. Değilse kuyruğu 15'e tamamlayacak kadar, **en fazla 5** yeni gönderi hazırla (aşağıdaki adımlar). Ör. kuyrukta 8 varsa 5, 12 varsa 3 gönderi.
3. Her gönderiyi `python tools/render.py queue/<klasör>` ile üret. `OVERFLOW` hatası verirse metni kısaltıp tekrar dene.
4. Üretilen `a.jpg` ve `b.jpg` dosyalarını **Read aracıyla açıp gözle kontrol et:** Fotoğrafta hayvan net görünmeli, kesilmemeli ve yazılarla çakışmamalı. Sorun varsa kırpmayı (`cx`, `cy`, `zoom`) ya da fotoğrafı değiştir.
5. Kaynak fotoğrafları (`photo_*.jpg`) sil. Depoda sadece `post.json`, `a.jpg` ve `b.jpg` kalmalı.
6. Canlıların adlarını `data/used.txt` sonuna ekle.
7. `git add -A && git commit -m "Yeni gönderiler: <adlar>" && git push` (çakışma olursa `git pull --rebase` sonra tekrar push).

**Hedefe ulaşmadan bitirme (sahibinin kuralı):** Günde 5 gönderi ve 3 Reels paylaşılıyor; kuyruk boşalırsa paylaşım kaçar.
- **Sıra:** `queue_reels/` içinde 4'ten az Reels varsa **önce Reels'i** hazırla, sonra gönderileri.
- **Paylaşılamayanlar:** `queue_failed/` ya da `queue_reels_failed/` içinde klasör varsa (Actions iki kez paylaşamayıp oraya koydu), önce onlara bak. Sorun içerikteyse (bozuk fotoğraf adresi, eksik dosya, çok uzun açıklama, ses metni) düzelt ve `git mv` ile `queue/` ya da `queue_reels/` içine adı `zz_` olmadan geri koy; düzeltemiyorsan olduğu gibi bırak, yerine yenisini hazırla ve son mesajında yaz. Sorun içerikte değilse (Instagram geçici hatası) aynen geri koy.
- Bir aday canlının fotoğrafı kötüyse ya da indirme takılırsa o canlıyı bırak ve **hemen başka bir canlı dene**. Bir canlıyı elemek çalışmayı bitirme sebebi değildir; hedef sayıya ulaşana kadar yeni adaylarla devam et (gerekirse 15-20 aday dene).
- Commons yavaşsa iNaturalist'e, iNaturalist'te iyi foto yoksa Commons'ta farklı arama sözcüklerine (İngilizce ad, cins adı) geç. Uzun indirmeleri arka plana atma; tek tek, `timeout 120` ile indir.
- Sadece iki kaynak da 30 dakikadan uzun süre hiç cevap vermiyorsa erken bitirebilirsin; o zaman son mesajında bunu açıkça yaz.

## 0. Önce performans raporunu ve öğrenme günlüğünü oku

`data/insights.md` her sabah 05:05'te gerçek Instagram istatistiklerinden yeniden üretilir; `data/learnings.md` senin önceki günlerde çıkardığın derslerdir. Canlı seçmeden ve metin yazmadan **önce** ikisini de oku.

Raporu doğru yorumla:
- **"İçerik" sütunu esastır.** Bir paylaşımın erişimi yüksekse önce **"Gün"** sütununa bak: gün etkisi ≥1,30 ise o gün her şey iyi gitmiştir (hareketli gün, reklam, algoritma). O paylaşımın başarısını içeriğe yazma. İçerik değeri ≥1,20 olanlar gerçekten etkileyici içeriktir.
- **Skor** paylaşım, kaydetme, beğeni ve (Reels'te) izlenme süresini de içerir. Büyüme için en değerli sinyaller sırasıyla: takip/1000, paylaşım/1000, kaydetme/1000, izlenme süresi, beğeni.
- Tablolardaki **"güçlü — daha sık kullan"** değerlere (canlı grubu, kanca tarzı, gün, saat, müzik, Reels süresi) ağırlık ver; **"zayıf"** olanları daha seyrek kullan (tamamen bırakma). "Veri yetersiz" olanları denemeye devam et.
- **Öne çıkan bulgular** listesini uygula. Örneğin "en çok paylaşılan Reels'in kancası X" diyorsa bugün o etkide yeni bir kanca dene; "Reels süresi >50 sn zayıf" diyorsa metni kısa tut.
- Hazırladığın gönderilerin yaklaşık **üçte ikisi** güçlü/ortalama tarzlarla, **üçte biri** keşif amaçlı (az denenmiş grup veya kanca) olsun (5 gönderide 3-4 güçlü, 1-2 keşif). Reels'te de güçlü tarzlara ağırlık ver, arada farklısını dene.
- "En iyi 5" başlıklarının **neden** tuttuğunu düşün (rakam mı, şaşkınlık mı, tehlike mi, benzetme mi) ve benzer etkide **yeni** başlıklar yaz. Kopyalama. "En zayıf 5"teki hatalardan kaçın.
- Rapor yoksa ya da veri azsa grupları ve kanca tarzlarını dengeli dağıt.
- Rapor **sadece** canlı seçimini, canlı grubunu, kanca tarzını, başlık/metin ifadesini, Reels metin uzunluğunu ve müzik seçimini etkiler. Tasarım şablonu (`assets/`, `tools/render.py`, `tools/reel.py`: yazı tipleri, renkler, yerleşim, rozet, kapak düzeni) **asla** değişmez, rapor ne derse desin.

**Öğrenme günlüğü:** Her çalıştırmanın sonunda `data/learnings.md` dosyasının **sonuna** 2-4 satır ekle ve commit'le:
```
## <YYYY-MM-DD>
- Rapordan öğrenilen: <en önemli 1-2 bulgu, sayılarıyla>
- Bugün uygulanan: <seçimlere nasıl yansıttın>
- Sonra kontrol et: <bu değişikliğin işe yarayıp yaramadığını görmek için neye bakılmalı>
```
Önceki günlerin "Sonra kontrol et" notlarına raporda bak; işe yaramayan bir değişikliği geri al, işe yarayanı sürdür. Dosya 60 günlük girdiyi aşarsa en eski girdileri tek bir "Özet" bölümünde birleştir.

Son mesajında, rapordan ne öğrendiğini ve seçimlerine nasıl yansıttığını kısaca yaz.

Her `post.json` ve `reel.json` dosyasına bu iki alanı **mutlaka** ekle (analiz bunlarla yapılıyor):
- `"group"`: `memeli` | `kuş` | `sürüngen` | `amfibi` | `balık` | `deniz omurgasızı` | `böcek/örümcek` | `diğer`
- `"hook_style"`: `sayı` (rakamlı iddia: "350 KİLO") | `süperlatif` ("dünyanın en...") | `tuhaf yetenek` (beklenmedik davranış/yetenek) | `tehlike` (zehir, ölümcül, saldırı) | `gizem` (az bilinen, yeni keşif, kayıp tür) | `benzetme` ("X gibi ama Y") | `tuhaf görünüm` (garip vücut, organ)

## 1. Canlı seçimi

- `data/used.txt` içindeki **hiçbir canlıyı seçme.** Emin olmak için canlının Türkçe, İngilizce ve bilimsel adını `data/instagram_posts.txt` içinde de ara (grep, büyük/küçük harf duyarsız). Bulursan seçme. Aynı canlının farklı bir türünü de seçme (ör. "kasuar" varsa "kuzey kasuarı" da olmaz).
- Hesabın tarzı: **vahşi doğadan, az bilinen, "bu gerçek mi?" dedirten** canlılar. Fotoğrafta çarpıcı duranları tercih et: memeliler, kuşlar, sürüngenler, balıklar, büyük böcekler, deniz canlıları.
- Mikroskobik canlılar, sadece mikroskop görüntüsü olanlar ve çok bilinen hayvanlar (aslan, kedi, köpek vb.) olmaz.
- Çeşitlilik olsun: bir çalıştırmada hazırladıkların arasında aynı gruptan en fazla 2 canlı olsun (ör. üç kuş olmaz); kuyruktaki son gönderilerle de art arda aynı grup gelmesin.
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
- **Yedek kaynak: iNaturalist.** Commons hız sınırına takılırsa (429, `download failed`, bir indirme ~3 dakikada bitmiyorsa) Commons'ta ısrar etme ve bekleme; hemen `python tools/commons.py inat "<bilimsel ad>"` ile iNaturalist'te ara. Commons'ta canlının yeterli iyi fotoğrafı yoksa da buraya bak. Liste yalnızca türü topluluk tarafından doğrulanmış (research grade) gözlemlerden CC0 / CC BY / CC BY-SA fotoğrafları gösterir; CC0 olanlar `[PD]` işaretlidir. Satırın sonundaki adresi indir: `python tools/commons.py download "https://inaturalist-open-data.s3.amazonaws.com/photos/.../original.jpeg" queue/<klasör>/photo_cover.jpg`. Yazar ve lisansı arama satırından alıp `credits`'e yaz (kaynak: iNaturalist). Aynı telif kuralları geçerli; tuzak, kafes, elde tutulan veya ölü hayvan fotoğrafını kullanma. Reels'te `photos` listesine `File:...` yerine bu adres yazılabilir.
- Bir gün fotoğraf sorunu yüzünden kuyruğu boş bırakmak yerine kaynakları birlikte kullan: aynı gönderide Commons ve iNaturalist fotoğrafları karışık olabilir.

## 3. Bilgiler (doğruluk — çok önemli)

- Her iddiayı güvenilir kaynaktan doğrula: Wikipedia (İngilizce), IUCN, Britannica, üniversite veya müze sayfaları. Emin olmadığın sayıyı yazma.
- Doğrulama ZORUNLU: Her canlı için en az İngilizce Wikipedia sayfasını oku (WebFetch aracıyla `https://en.wikipedia.org/wiki/<Bilimsel_ad>`, olmazsa `curl`). Kapak başlığındaki ve kartlardaki her sayı ve iddia o sayfada (veya başka güvenilir kaynakta) geçmeli. Hiçbir kaynağa erişemiyorsan o gün gönderi üretme ve son mesajında bunu açıkça yaz.
- Abartma: "mermi hızında", "en ölümcül" gibi ifadeleri sadece kaynak öyle diyorsa kullan.
- Kapak başlığı, hayvanın en şaşırtıcı ve doğrulanmış tek özelliği olmalı.

## 4. post.json formatı

Klasör adı: `queue/<YYYYMMDD>-<nn>_<ad>` (ör. `queue/20261105-01_babirusa`). Burada nn iki haneli sıra numarası (01, 02 …); aynı tarihte klasör varsa kaldığı yerden devam et (sabah 01-05, öğlen 06-07 gibi). Ad küçük harf ve Türkçe karaktersiz. Tarih, gönderinin hazırlandığı gün.

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
  Fotoğraf iNaturalist'tense sonu `/ iNaturalist` olur; ikisi karışıksa `📷 <Yazar> (<Lisans>) / Wikimedia Commons, <Yazar> (<Lisans>) / iNaturalist`.
  Aynı yazar birden fazla fotoğrafta varsa bir kez yaz. Tamamı kamu malıysa kaynak satırı ekleme.

## 6. Reels (her gün 10:30, 13:30, 20:00)

`queue_reels/` klasörüne bak. **9'dan az Reels varsa (3 günlük yedek) kuyruğu 9'a tamamlayacak kadar, en fazla 3 yeni Reels tarifi hazırla.** Her biri farklı canlı ve farklı grup olsun (ör. bir memeli, bir kuş, bir sürüngen); kanca tarzlarını ve müzikleri de çeşitlendir. Videoyu sen üretmiyorsun; GitHub Actions paylaşımdan hemen önce `tools/reel.py` ile üretiyor. Sen tarifi (`reel.json`) ve kapağı (`cover.jpg`) hazırlarsın.

- **Canlı:** Aynı yasak listesi (`data/used.txt` + `data/instagram_posts.txt`). Bu çalıştırmada gönderiler için seçtiğin canlılardan da farklı olmalı. En az 7 iyi fotoğrafı olan canlı seç (mümkünse doğal ortamda çekilmiş). Telif kuralları gönderilerle aynı.
- **Klasör:** `queue_reels/<YYYYMMDD>-<nn>_<ad>` (nn iki haneli sıra, aynı tarihte varsa devam et; Türkçe karaktersiz, küçük harf).
- **Metin:** 8-9 kısa cümle, toplam **70-85 kelime** (son cümle dahil). Video 35-45 saniye olmalı; 85 kelimeyi aşma (gelada Reels'i 100+ kelimeyle 54 saniye sürdü, fazla uzun). Her bilgi Wikipedia'dan doğrulanmış olmalı. 1. cümle kanca: en şaşırtıcı bilgi. **Son cümle her zaman aynen:** `Canlılar hakkında daha fazla bilgi alabilmek için bizi takip etmeyi unutmayın.` Belgesel anlatıcısı tonu; kısa, akıcı cümleler.
- **Sahneler:** Her cümle bir sahne, her sahnede farklı fotoğraf. Yatay fotoğraflarda `pan_left`/`pan_right` (kamera hayvanın üzerinde kayar), dikey fotoğraflarda `zoom_in`/`zoom_out`. `cx`, `cy` hayvanın (tercihen başının) konumu.
- **Müzik:** Ruh haline göre biri: `assets/music/Reawakening.mp3` (sakin, görkemli), `assets/music/Investigations.mp3` (gizemli), `assets/music/Ancient_Rite.ogg` (vahşi, enerjik). `"loudness": -27`.
- **Kapak:** Hayvanın net ve büyük göründüğü fotoğraf. Başlık **tam 4 satır** (bütün kapaklar aynı görünsün diye), satır başına en fazla **~11 karakter**, büyük harf; ilk ve/veya son satır kırmızı (`R`), diğerleri beyaz (`W`). Kısa, çarpıcı bir kanca (ör. `350 KİLO / AMA İKİ / AYAK ÜSTÜNDE / DURABİLİYOR`). Kapak düzeni sabittir: yazı boyutu, rozet ve başlığın yeri her kapakta aynı, küçülmez. `--cover` komutu `COVER OVERFLOW` hatası verirse o satırı kısalt ya da kelimeyi alt satıra al.
- **Açıklama (`caption`):** Tek cümle + 2 emoji, boş satır, `#terrawildnature #<canlıadı>`, boş satır; kamu malı olmayan fotoğraf varsa `📷 <Yazar> (<Lisans>) / Wikimedia Commons` (iNaturalist fotoğrafıysa `/ iNaturalist`); son satır her zaman `🎵 Kevin MacLeod (CC BY)`.
- `credits` alanına her fotoğrafın yazarını ve lisansını yaz.
- **`yt_title`:** Aynı video YouTube Shorts olarak da yayınlanıyor. Ona kısa bir başlık yaz (en fazla 60 karakter, ilk harfler büyük, canlının adı geçsin, merak uyandırsın, yalan abartı olmasın). Ör. `"Dünyanın En Büyük Maymunu: Mandril"`, `"Bu Kuşun Yuvası Bir İnsanı Taşıyabiliyor"`. `#shorts` ekleme, araç ekliyor.
- **`en` (İngilizce başlık/açıklama, zorunlu):** `"en": {"title": "The World's Largest Monkey: Mandrill", "description": "<caption cümlesinin akıcı İngilizcesi, emojisiz>"}`. Başlık ≤60 karakter, İngilizce yaygın adı geçsin, `#shorts` yok. İngilizce YouTube kullanan izleyiciler bunu görür.
- **Kontrol:** `python tools/reel.py --preview queue_reels/<klasör>` ve `python tools/reel.py --cover queue_reels/<klasör>` çalıştır (fotoğrafları `photos` listesinden kendisi indirir). `preview.jpg` ve `cover.jpg` dosyalarını Read ile aç: hayvan her karede görünmeli, başı kesilmemeli, kapak başlığı okunaklı ve ortada olmalı. Sorun varsa düzelt ve tekrar üret.
- Sonra `p*.jpg` ve `preview.jpg` dosyalarını sil. Klasörde sadece `reel.json` ve `cover.jpg` kalmalı. `data/used.txt` sonuna `<ad> (Reels) | <bilimsel ad>` ekle.

Örnek: `queue_reels/20261023_takin/reel.json` (bu dosya paylaşılınca `posted_reels/` altına taşınır; orada da bakabilirsin).

## Asla yapma

- Instagram'a doğrudan paylaşım yapma. `tools/publish.py` dosyasını çalıştırma.
- `queue/` içinde var olan gönderileri silme veya değiştirme (sen bu çalıştırmada eklemediysen).
- `assets/`, `tools/` ve `.github/` dosyalarını değiştirme. Bir hata bulursan son mesajında açıkla.
