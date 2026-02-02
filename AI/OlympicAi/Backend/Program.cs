using Scalar.AspNetCore;
using AI_spotter.Controllers;
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddHttpClient<IAiClientConnect, AiClientConnect>()
    .ConfigureHttpClient(client =>
    {
        // Set a 10-minute timeout for video processing
        client.Timeout = TimeSpan.FromMinutes(10);
    });
// Add services to the container.
builder.Services.AddControllers();
// Learn more about configuring OpenAPI at https://aka.ms/aspnet/openapi
builder.Services.AddOpenApi();

var app = builder.Build();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
    app.MapScalarApiReference();
}

app.UseHttpsRedirection();

// app.UseAuthorization();

app.MapControllers();

app.Run();
