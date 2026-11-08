# Damla damla kurtararak göl oluşur

NOT: Bu proje geliştirilme aşamasında ve zaman kazanmak için tamamen AI ile hazırlandı ilk versiyon. Düzeltmeler yapıldıktan sonra uygulamanın kodları sonradan inceleyip özümseyeceğim. Bu hali en iyi hali değil ve geliştirilecek.


Kodland M10 mezuniyet projesi. `diary-tur-main` günlük fikri ile `TUR_Calculator-main` eko hesaplayıcısını tek bir Flask uygulamasında birleştirir.

## Çalıştırma

1. Terminalde bu klasöre geçin.
2. Gerekli paketleri kurun:

   ```bash
   python3 -m pip install -r requirements.txt
   ```

3. Uygulamayı başlatın:

   ```bash
   python3 main.py
   ```

4. Tarayıcıda `http://127.0.0.1:5000` adresini açın.

İlk çalıştırmada `instance/eco_diary.db` oluşturulur. Ad, soyad ve e-posta ile ilk test kaydı açılır. Aynı e-posta ile yeniden giriş yapıldığında yeni sonuç önceki testle karşılaştırılır. Sonuç ayrıca günlük kartı olarak kaydedilir. Dashboard'daki **Takip testini simüle et** düğmesi, bir hafta beklemeden takip akışını denemeyi sağlar; gerçek takip tarihi her kayıt için yedi gün sonrasına yazılır.

## Akış

- Ana sayfa: iklim değişikliğinin boyutunu ve projenin amacını anlatır.
- Kimlik: ilk/geri dönen kullanıcıyı e-posta ile bulur.
- Eko hesaplayıcı: ev büyüklüğü, lamba ve elektrikli cihaz sayısını sorar.
- Sonuç: az/orta/çok elektrik etkisi, güçlü alanlar ve kişisel öneriler verir.
- İlerlemem: tarihçe, puan farkı ve takip tarihi.
- Günlüğüm: her test sonucunu ve manuel notları kart olarak saklar.

## Kaynak projelerden düzeltilen noktalar

- Calculator içindeki eksik Jinja rotaları gerçek Flask rotalarıyla değiştirildi.
- Orta/büyük ev seçenekleri ve tüm lamba/cihaz seçenekleri tamamlandı.
- Diary'deki `/card/<id>` detay rotası gerçek kaydı gösterecek şekilde düzeltildi.
- İki ayrı uygulama tek sunucu ve tek SQLite veritabanında birleştirildi.
