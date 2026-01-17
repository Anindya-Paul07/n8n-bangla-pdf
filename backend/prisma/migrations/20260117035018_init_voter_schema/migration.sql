-- CreateTable
CREATE TABLE "Voter" (
    "id" SERIAL NOT NULL,
    "name" TEXT NOT NULL,
    "voterNo" TEXT NOT NULL,
    "address" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Voter_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "Voter_voterNo_key" ON "Voter"("voterNo");
