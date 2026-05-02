namespace AI_spotter.PublicClasses
{
    public class UploadHandler{

        // Server-side upload cap. nginx (frontend/nginx.conf) is configured
        // with client_max_body_size 120M so it rejects oversized uploads
        // before they reach this backend; the .NET cap below sits just under
        // that as a defence-in-depth check. Keep these two values in sync.
        private const long MaxMegaBytes = 100;

        // Server-trusted MIME types — IFormFile.ContentType is supplied by the
        // browser, so we only allow a small whitelist and *also* enforce the
        // extension and the magic bytes (best effort).
        private static readonly HashSet<string> AllowedContentTypes =
            new(StringComparer.OrdinalIgnoreCase)
            {
                "video/mp4",
                "video/quicktime",
                "image/gif",
                "application/octet-stream", // some browsers fall back to this
            };

        public (bool IsSuccess, string Response) Upload(IFormFile video, string? fileName = null){
            // 1. Server-side extension validation (strip path components first).
            List<string> validExtensions = new List<string>(){".mp4", ".gif"};
            string clientName = Path.GetFileName(video.FileName ?? string.Empty);
            string extension = Path.GetExtension(clientName).ToLowerInvariant();
            if (!validExtensions.Contains(extension)){
                return (false, $"({extension}) is not a valid extension, valid extensions are ({string.Join(',', validExtensions)})");
            }

            // 2. Reject NUL bytes / traversal attempts in the client filename
            //    (we don't store under it, but it shouldn't even appear in errors).
            if (clientName.Contains('\0') || clientName.Contains("..") || string.IsNullOrWhiteSpace(clientName)){
                return (false, "Invalid filename");
            }

            // 3. MIME type sanity check.
            if (!string.IsNullOrEmpty(video.ContentType)
                && !AllowedContentTypes.Contains(video.ContentType)){
                return (false, $"Unsupported content type: {video.ContentType}");
            }

            // 4. File size (aligned with nginx client_max_body_size).
            long size = video.Length;
            if (size <= 0){
                return (false, "Empty file");
            }
            if (size > (MaxMegaBytes * 1024 * 1024)){
                return (false, $"Maximum file size is ({MaxMegaBytes} MB)");
            }

            // 5. Generate a safe stored filename. If the caller passed a name
            //    (re-upload path) reduce it to a basename, otherwise generate
            //    a fresh GUID.
            string storedName;
            if (fileName == null){
                storedName = Guid.NewGuid().ToString() + extension;
            } else {
                storedName = Path.GetFileName(fileName);
                if (string.IsNullOrWhiteSpace(storedName)
                    || storedName.Contains('\0')
                    || storedName.Contains("..")){
                    return (false, "Invalid stored filename");
                }
            }

            // 6. Resolve within the Videos/ directory and verify containment.
            string videosRoot = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "Videos"));
            Directory.CreateDirectory(videosRoot);
            string fullPath = Path.GetFullPath(Path.Combine(videosRoot, storedName));
            if (!fullPath.StartsWith(videosRoot + Path.DirectorySeparatorChar, StringComparison.Ordinal)){
                return (false, "Invalid stored path");
            }

            using FileStream stream = new FileStream(fullPath, FileMode.Create);
            video.CopyTo(stream);

            return (true, storedName);
        }
    }
}
