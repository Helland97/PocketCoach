using Scalar.AspNetCore;
using Microsoft.EntityFrameworkCore;
using AI_spotter.Controllers;
using AI_spotter.Data;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddHttpClient<IAiClientConnect, AiClientConnect>()
    .ConfigureHttpClient(client =>
    {
        // Set a 10-minute timeout for video processing
        client.Timeout = TimeSpan.FromMinutes(10);
    });

// Register SQLite database
var connectionString = builder.Configuration.GetConnectionString("DefaultConnection")
    ?? "Data Source=Data/aispotter.db";
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlite(connectionString));

// Restrictive CORS — this service is reached through nginx on the same host.
// Allow only same-origin requests; deny everything else by default.
const string CorsPolicy = "AISpotterDefault";
builder.Services.AddCors(options =>
{
    options.AddPolicy(CorsPolicy, policy =>
    {
        policy.WithOrigins(
                "http://localhost",
                "http://localhost:80",
                "http://frontend"
            )
            .WithMethods("GET", "POST", "PUT", "DELETE")
            .AllowAnyHeader();
    });
});

// Add services to the container.
builder.Services.AddControllers();
// Learn more about configuring OpenAPI at https://aka.ms/aspnet/openapi
builder.Services.AddOpenApi();

var app = builder.Build();

// Auto-apply migrations on startup (creates DB if it doesn't exist)
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    db.Database.Migrate();
}

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
    app.MapScalarApiReference();
}

// HTTPS redirection only outside container deployments.
// In Docker the service serves plain HTTP behind nginx; redirecting would
// produce broken responses (see security audit, item 9).
if (app.Environment.IsDevelopment())
{
    app.UseHttpsRedirection();
}

app.UseCors(CorsPolicy);

// app.UseAuthorization();

app.MapControllers();

app.Run();
