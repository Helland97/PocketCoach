using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace AI_spotter.Migrations
{
    /// <inheritdoc />
    public partial class InitialCreate : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "Sessions",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    ExerciseType = table.Column<string>(type: "TEXT", nullable: false),
                    CameraAngle = table.Column<string>(type: "TEXT", nullable: false),
                    NReps = table.Column<int>(type: "INTEGER", nullable: false),
                    CreatedAt = table.Column<string>(type: "TEXT", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Sessions", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Analyses",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    SessionId = table.Column<int>(type: "INTEGER", nullable: false),
                    BiomechanicalData = table.Column<byte[]>(type: "BLOB", nullable: false),
                    BiomechanicalShape = table.Column<string>(type: "TEXT", nullable: false),
                    FeatureNames = table.Column<string>(type: "TEXT", nullable: false),
                    ComparisonResult = table.Column<string>(type: "TEXT", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Analyses", x => x.Id);
                    table.ForeignKey(
                        name: "FK_Analyses_Sessions_SessionId",
                        column: x => x.SessionId,
                        principalTable: "Sessions",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateTable(
                name: "Landmarks",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    SessionId = table.Column<int>(type: "INTEGER", nullable: false),
                    Data = table.Column<byte[]>(type: "BLOB", nullable: false),
                    Shape = table.Column<string>(type: "TEXT", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Landmarks", x => x.Id);
                    table.ForeignKey(
                        name: "FK_Landmarks_Sessions_SessionId",
                        column: x => x.SessionId,
                        principalTable: "Sessions",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateIndex(
                name: "IX_Analyses_SessionId",
                table: "Analyses",
                column: "SessionId",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_Landmarks_SessionId",
                table: "Landmarks",
                column: "SessionId",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_Sessions_CreatedAt",
                table: "Sessions",
                column: "CreatedAt");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "Analyses");

            migrationBuilder.DropTable(
                name: "Landmarks");

            migrationBuilder.DropTable(
                name: "Sessions");
        }
    }
}
