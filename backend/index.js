// backend/index.js
require('dotenv').config();
const express = require('express');
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

// Search voters (query param can match name, voterNo, or address)
app.get('/voters', async (req, res) => {
  const { query } = req.query;
  if (!query) {
    const all = await prisma.voter.findMany();
    return res.json(all);
  }
  const results = await prisma.voter.findMany({
    where: {
      OR: [
        { name: { contains: query, mode: 'insensitive' } },
        { voterNo: { contains: query, mode: 'insensitive' } },
        { address: { contains: query, mode: 'insensitive' } },
      ],
    },
  });
  res.json(results);
});

// Add new voter
app.post('/voters', async (req, res) => {
  const { name, voterNo, address } = req.body;
  if (!name || !voterNo || !address) {
    return res.status(400).json({ error: 'name, voterNo and address are required' });
  }
  try {
    const newVoter = await prisma.voter.create({
      data: { name, voterNo, address },
    });
    res.status(201).json(newVoter);
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: 'Failed to create voter' });
  }
});

// Generate voter slip PDF (placeholder – returns JSON for now)
app.get('/voters/:id/slip', async (req, res) => {
  const { id } = req.params;
  const voter = await prisma.voter.findUnique({ where: { id: Number(id) } });
  if (!voter) {
    return res.status(404).json({ error: 'Voter not found' });
  }
  // TODO: integrate pdf generation (e.g., pdfkit) and send as application/pdf
  res.json({ message: 'PDF slip generation not implemented yet', voter });
});

app.listen(PORT, () => {
  console.log(`Backend server listening on http://localhost:${PORT}`);
});
