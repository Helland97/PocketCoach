namespace AI_spotter.Data;

using Microsoft.EntityFrameworkCore;
using AI_spotter.Models;

public class AppDbContext : DbContext
{
    public DbSet<Session> Sessions { get; set; }
    public DbSet<LandmarkData> Landmarks { get; set; }
    public DbSet<Analysis> Analyses { get; set; }

    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        // Session -> LandmarkData (one-to-one, no cascade delete)
        modelBuilder.Entity<Session>()
            .HasOne(s => s.Landmark)
            .WithOne(l => l.Session)
            .HasForeignKey<LandmarkData>(l => l.SessionId)
            .OnDelete(DeleteBehavior.Restrict);

        // Session -> Analysis (one-to-one, no cascade delete)
        modelBuilder.Entity<Session>()
            .HasOne(s => s.Analysis)
            .WithOne(a => a.Session)
            .HasForeignKey<Analysis>(a => a.SessionId)
            .OnDelete(DeleteBehavior.Restrict);

        // Index on CreatedAt for ordering queries
        modelBuilder.Entity<Session>()
            .HasIndex(s => s.CreatedAt);
    }
}
