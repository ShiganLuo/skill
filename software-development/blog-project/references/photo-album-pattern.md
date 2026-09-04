# Photo Album Implementation Pattern

## Database Schema

```sql
CREATE TABLE photo_album (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    album_name VARCHAR(100) NOT NULL,
    description VARCHAR(500) DEFAULT NULL,
    album_cover VARCHAR(500) DEFAULT NULL,  -- relative path
    sort_order INT NOT NULL DEFAULT 0,
    is_visible TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE photo_album_images (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    album_id BIGINT NOT NULL,
    image_id BIGINT NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_album_image (album_id, image_id),
    CONSTRAINT fk_pai_album FOREIGN KEY (album_id) REFERENCES photo_album(id) ON DELETE CASCADE,
    CONSTRAINT fk_pai_image FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## Backend Files

- Entity: `PhotoAlbum.java`
- DTO: `PhotoAlbumDTO.java` (AlbumListResponse, AlbumDetailResponse, AlbumPhoto, AddAlbumRequest, UpdateAlbumRequest, AddImageToAlbumRequest)
- Mapper: `PhotoAlbumMapper.java` + `PhotoAlbumMapper.xml`
- Service: `PhotoAlbumService.java` + `PhotoAlbumServiceImpl.java`
- Controllers: `FrontPhotoAlbumController.java` (public), `AdminPhotoAlbumController.java` (admin CRUD)

## Frontend Files

- API: `photoApi.ts` (getAllAlbum, getAlbumById, adminGetAllAlbum, addAlbum, updateAlbum, deleteAlbum, addImageToAlbum, removeImageFromAlbum)
- Types: `types/photo.ts` (Album, AlbumPhoto, AlbumDetail)
- Pages: `photo-album.vue` (album grid), `photos.vue` (album detail with photos)
- Admin: `photo/index.vue` (album management with ImagePicker)

## Key Pattern

Images and albums are separate entities linked via junction table. This allows:
- Images to exist without albums (素材库)
- Images to be in multiple albums
- Albums to have metadata (name, description, cover) independent of images

## API Response Formats

**Album list** (`/admin/photoAlbum/list`):
```json
{ "code": 200, "result": [{ "id": 1, "albumName": "...", "albumCover": "...", "photoCount": 5 }] }
```

**Album detail** (`/admin/photoAlbum/{id}`):
```json
{ "code": 200, "result": { "id": 1, "albumName": "...", "albumCover": "...", "photos": [{ "imageId": 1, "filePath": "/my-bucket/uuid.jpg", "fileName": "xxx.jpg", "sortOrder": 0 }] }}
```

Note: `photos` is an array directly in `result`, NOT `{ list: [...], total: N }`. Frontend code must access `res.result.photos` not `res.result.list`.

## Pitfalls

1. **Admin route**: Album list route is `/photo/index`, album detail route is `/photo/photo/:albumId` (with `isHide: true` in meta). Click handler on album card must navigate to detail page.
2. **Cover URL**: Album covers stored as relative paths. Use `getCoverUrl(cover)` helper that prepends `VITE_MINIO_URL` env var. Production value: `https://minio.shiganluo.top`.
3. **Frontend env**: `VITE_MINIO_URL` must be in both `.env.development` (http://127.0.0.1:9007) and `.env.production` (https://minio.shiganluo.top). Missing this causes localhost URLs in production.
4. **Page rewrite**: When rewriting admin pages, always preserve click handlers (`@click`, `router.push`). Grep old version for interactive elements before rewriting.
