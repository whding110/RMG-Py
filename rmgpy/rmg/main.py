#!/usr/bin/python
# -*- coding: utf-8 -*-

################################################################################
#
#   RMG - Reaction Mechanism Generator
#
#   Copyright (c) 2002-2010 Prof. William H. Green (whgreen@mit.edu) and the
#   RMG Team (rmg_dev@mit.edu)
#
#   Permission is hereby granted, free of charge, to any person obtaining a
#   copy of this software and associated documentation files (the 'Software'),
#   to deal in the Software without restriction, including without limitation
#   the rights to use, copy, modify, merge, publish, distribute, sublicense,
#   and/or sell copies of the Software, and to permit persons to whom the
#   Software is furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#   FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#   DEALINGS IN THE SOFTWARE.
#
################################################################################

"""
This module contains the main execution functionality for Reaction Mechanism
Generator (RMG).
"""

import os.path
import sys
import logging
import time
import shutil

from rmgpy.data.rmg import RMGDatabase

from model import Species
from pdep import PDepNetwork

################################################################################

class RMG:
    """
    A representation of a Reaction Mechanism Generator (RMG) job. The 
    attributes are:
    
    =========================== ================================================
    Attribute                   Description
    =========================== ================================================
    `inputFile`                 The path to the input file
    `logFile`                   The path to the log file
    --------------------------- ------------------------------------------------
    `databaseDirectory`         The directory containing the RMG database
    `thermoLibraries`           The thermodynamics libraries to load
    `reactionLibraries`         The kinetics libraries to load
    `statmechLibraries`         The statistical mechanics libraries to load
    `seedMechanisms`            The seed mechanisms included in the model
    `kineticsDepositories`      The kinetics depositories to use for looking up kinetics in each family
    `kineticsEstimator`         The method to use to estimate kinetics: 'group additivity' or 'rate rules'
    --------------------------- ------------------------------------------------
    `reactionModel`             The core-edge reaction model generated by this job
    `reactionSystems`           A list of the reaction systems used in this job
    `database`                  The RMG database used in this job
    --------------------------- ------------------------------------------------
    `absoluteTolerance`         The absolute tolerance used in the ODE/DAE solver
    `relativeTolerance`         The relative tolerance used in the ODE/DAE solver
    `fluxToleranceKeepInEdge`   The relative species flux below which species are discarded from the edge
    `fluxToleranceMoveToCore`   The relative species flux above which species are moved from the edge to the core
    `fluxToleranceInterrupt`    The relative species flux above which the simulation will halt
    `maximumEdgeSpecies`        The maximum number of edge species allowed at any time
    `termination`               A list of termination targets (i.e :class:`TerminationTime` and :class:`TerminationConversion` objects)
    --------------------------- ------------------------------------------------
    `outputDirectory`           The directory used to save output files
    `scratchDirectory`          The directory used to save temporary files
    `verbosity`                 The level of logging verbosity for console output
    `loadRestart`               ``True`` if restarting a previous job, ``False`` otherwise
    `saveRestartPeriod`         The time period to periodically save a restart file (:class:`Quantity`), or ``None`` for never.
    `units`                     The unit system to use to save output files (currently must be 'si')
    `drawMolecules`             ``True`` to draw pictures of the species in the core, ``False`` otherwise
    `generatePlots`             ``True`` to generate plots of the job execution statistics after each iteration, ``False`` otherwise
    `pressureDependence`        Whether to process unimolecular (pressure-dependent) reaction networks
    `wallTime`                  The maximum amount of CPU time in seconds to expend on this job; used to stop gracefully so we can still get profiling information
    --------------------------- ------------------------------------------------
    `initializationTime`        The time at which the job was initiated, in seconds since the epoch (i.e. from time.time())
    =========================== ================================================
    
    """
    
    def __init__(self, inputFile=None, logFile=None, outputDirectory=None, scratchDirectory=None):
        self.inputFile = inputFile
        self.logFile = logFile
        self.outputDirectory = outputDirectory
        self.scratchDirectory = scratchDirectory
        self.clear()
    
    def clear(self):
        """
        Clear all loaded information about the job (except the file paths).
        """
        self.databaseDirectory = None
        self.thermoLibraries = None
        self.reactionLibraries = None
        self.statmechLibraries = None
        self.seedMechanisms = None
        self.kineticsDepositories = None
        self.kineticsEstimator = 'group additivity'
        
        self.reactionModel = None
        self.reactionSystems = None
        self.database = None
        
        self.fluxToleranceKeepInEdge = 0.0
        self.fluxToleranceMoveToCore = 1.0
        self.fluxToleranceInterrupt = 1.0
        self.absoluteTolerance = 1.0e-8
        self.relativeTolerance = 1.0e-4
        self.maximumEdgeSpecies = 1000000
        self.termination = []
        
        self.verbosity = logging.INFO
        self.loadRestart = None
        self.saveRestartPeriod = None
        self.units = 'si'
        self.drawMolecules = None
        self.generatePlots = None
        self.saveConcentrationProfiles = None
        self.pressureDependence = None
        self.wallTime = 0
        self.initializationTime = 0
    
    def loadInput(self, path=None):
        """
        Load an RMG job from the input file located at `inputFile`, or
        from the `inputFile` attribute if not given as a parameter.
        """
        from input import readInputFile
        if path is None: path = self.inputFile
        readInputFile(path, self)
        self.reactionModel.kineticsEstimator = self.kineticsEstimator
        if self.pressureDependence:
            # If the output directory is not yet set, then set it to the same
            # directory as the input file by default
            if not self.outputDirectory:
                self.outputDirectory = os.path.dirname(path)
            self.pressureDependence.outputFile = self.outputDirectory
            self.reactionModel.pressureDependence = self.pressureDependence
        
    def saveInput(self, path=None):
        """
        Save an RMG job to the input file located at `path`, or
        from the `outputFile` attribute if not given as a parameter.
        """
        from input import saveInputFile
        if path is None: path = self.outputFile
        saveInputFile(path, self)
        
    def loadDatabase(self):
        
        self.database = RMGDatabase()
        self.database.load(
            path = self.databaseDirectory,
            thermoLibraries = self.thermoLibraries,
            reactionLibraries = [library for library, option in self.reactionLibraries],
            seedMechanisms = self.seedMechanisms,
            kineticsDepositories = self.kineticsDepositories,
            #frequenciesLibraries = self.statmechLibraries,
            depository = False, # Don't bother loading the depository information, as we don't use it
        )
    
    def execute(self, args):
        """
        Execute an RMG job using the command-line arguments `args` as returned
        by the :mod:`argparse` package.
        """
    
        # Save initialization time
        self.initializationTime = time.time()
    
        # Log start timestamp
        logging.info('RMG execution initiated at ' + time.asctime() + '\n')
    
        # Print out RMG header
        self.logHeader()
        
        # Set directories
        self.outputDirectory = args.output_directory
        self.scratchDirectory = args.scratch_directory
        
        # Read input file
        self.loadInput(args.file[0])
    
        # See if memory profiling package is available
        try:
            import os
            import psutil
        except ImportError:
            logging.info('Optional package dependency "psutil" not found; memory profiling information will not be saved.')
    
        # See if spreadsheet writing package is available
        if self.saveConcentrationProfiles:
            try:
                import xlwt
            except ImportError:
                logging.warning('Package dependency "xlwt" not found; reaction system concentration profiles will not be saved, despite saveConcentrationProfiles = True option.')
                self.saveConcentrationProfiles = False
        
        # Make output subdirectories
        self.makeOutputSubdirectory('plot')
        self.makeOutputSubdirectory('species')
        self.makeOutputSubdirectory('pdep')
        self.makeOutputSubdirectory('chemkin')
        self.makeOutputSubdirectory('solver')
        
        # Load databases
        self.loadDatabase()
    
        # Set wall time
        if args.walltime == '0': 
            self.wallTime = 0
        else:
            data = args.walltime[0].split(':')
            if len(data) == 1:
                self.wallTime = int(data[-1])
            elif len(data) == 2:
                self.wallTime = int(data[-1]) + 60 * int(data[-2])
            elif len(data) == 3:
                self.wallTime = int(data[-1]) + 60 * int(data[-2]) + 3600 * int(data[-3])
            elif len(data) == 4:
                self.wallTime = int(data[-1]) + 60 * int(data[-2]) + 3600 * int(data[-3]) + 86400 * int(data[-4])
            else:
                raise ValueError('Invalid format for wall time; should be HH:MM:SS.')
    
        # Delete previous HTML file
        from rmgpy.rmg.output import saveOutputHTML
        saveOutputHTML(os.path.join(self.outputDirectory, 'output.html'), self.reactionModel)
        
        # Initialize reaction model
        if args.restart:
            self.loadRestartFile(os.path.join(self.outputDirectory,'restart.pkl.gz'))
        else:
    
            # Seed mechanisms: add species and reactions from seed mechanism
            # DON'T generate any more reactions for the seed species at this time
            for seedMechanism in self.seedMechanisms:
                self.reactionModel.addSeedMechanismToCore(seedMechanism, react=False)

            # Reaction libraries: add species and reactions from reaction library to the edge so
            # that RMG can find them if their rates are large enough
            for library, option in self.reactionLibraries:
                self.reactionModel.addReactionLibraryToEdge(library)
            
            # Add nonreactive species (e.g. bath gases) to core first
            # This is necessary so that the PDep algorithm can identify the bath gas
            for spec in self.initialSpecies:
                if not spec.reactive:
                    self.reactionModel.enlarge(spec)
            # Then add remaining reactive species
            for spec in self.initialSpecies:
                spec.generateThermoData(self.database)
            for spec in self.initialSpecies:
                if spec.reactive:
                    self.reactionModel.enlarge(spec)
            
            # Save a restart file if desired
            if self.saveRestartPeriod:
                self.saveRestartFile(os.path.join(self.outputDirectory,'restart.pkl'), self.reactionModel)
    
        # RMG execution statistics
        coreSpeciesCount = []
        coreReactionCount = []
        edgeSpeciesCount = []
        edgeReactionCount = []
        execTime = []
        restartSize = []
        memoryUse = []
    
        # Main RMG loop
        done = False
        while not done:
    
            if self.saveConcentrationProfiles:
                workbook = xlwt.Workbook()
                
            done = True
            objectsToEnlarge = []
            allTerminated = True
            for index, reactionSystem in enumerate(self.reactionSystems):
    
                if self.saveConcentrationProfiles:
                    worksheet = workbook.add_sheet('#{0:d}'.format(index+1))
                else:
                    worksheet = None
                
                # Conduct simulation
                logging.info('Conducting simulation of reaction system %s...' % (index+1))
                terminated, obj = reactionSystem.simulate(
                    coreSpecies = self.reactionModel.core.species,
                    coreReactions = self.reactionModel.core.reactions,
                    edgeSpecies = self.reactionModel.edge.species,
                    edgeReactions = self.reactionModel.edge.reactions,
                    toleranceKeepInEdge = self.fluxToleranceKeepInEdge,
                    toleranceMoveToCore = self.fluxToleranceMoveToCore,
                    toleranceInterruptSimulation = self.fluxToleranceInterrupt,
                    termination = self.termination,
                    pdepNetworks = self.reactionModel.unirxnNetworks,
                    worksheet = worksheet,
                    absoluteTolerance = self.absoluteTolerance,
                    relativeTolerance = self.relativeTolerance,
                )
                allTerminated = allTerminated and terminated
                logging.info('')
                
                # If simulation is invalid, note which species should be added to
                # the core
                if obj:
                    if isinstance(obj, PDepNetwork):
                        # Determine which species in that network has the highest leak rate
                        # We do this here because we need a temperature and pressure
                        # Store the maximum leak species along with the associated network
                        obj = (obj, obj.getMaximumLeakSpecies(reactionSystem.T.value, reactionSystem.P.value))
                    objectsToEnlarge.append(obj)
                    done = False
    
            if self.saveConcentrationProfiles:
                workbook.save(os.path.join(self.outputDirectory, 'solver', 'simulation_{0:d}.xls'.format(len(self.reactionModel.core.species))))
    
            if not done:
    
                # If we reached our termination conditions, then try to prune
                # species from the edge
                if allTerminated:
                    self.reactionModel.prune(self.reactionSystems, self.fluxToleranceKeepInEdge, self.maximumEdgeSpecies)
    
                # Enlarge objects identified by the simulation for enlarging
                # These should be Species or Network objects
                logging.info('')
                objectsToEnlarge = list(set(objectsToEnlarge))
                for object in objectsToEnlarge:
                    self.reactionModel.enlarge(object)

            # If the user specifies it, add unused reaction library reactions to
            # an additional output species and reaction list which is written to the ouput HTML
            # file as well as the chemkin file
            self.reactionModel.outputSpeciesList = []
            self.reactionModel.outputReactionList = []
            for library, option in self.reactionLibraries:
                if option:
                    self.reactionModel.addReactionLibraryToOutput(library)
                    
            # Save the current state of the model core to a pretty HTML file
            logging.info('Saving latest model core to HTML file...')
            saveOutputHTML(os.path.join(self.outputDirectory, 'output.html'), self.reactionModel)
            
            # Save a Chemkin file containing the current model core
            logging.info('Saving latest model core to Chemkin file...')
            this_chemkin_path = os.path.join(self.outputDirectory, 'chemkin', 'chem%04i.inp' % len(self.reactionModel.core.species))
            latest_chemkin_path = os.path.join(self.outputDirectory, 'chemkin','chem.inp')
            latest_dictionary_path = os.path.join(self.outputDirectory, 'chemkin','species_dictionary.txt')
            self.reactionModel.saveChemkinFile(this_chemkin_path, latest_dictionary_path)
            if os.path.exists(latest_chemkin_path):
                os.unlink(latest_chemkin_path)
            os.link(this_chemkin_path,latest_chemkin_path)
    
            # Save the restart file if desired
            if self.saveRestartPeriod or done:
                self.saveRestartFile(os.path.join(self.outputDirectory,'restart.pkl'), self.reactionModel, delay=0 if done else self.saveRestartPeriod.value)

            # Update RMG execution statistics
            logging.info('Updating RMG execution statistics...')
            coreSpec, coreReac, edgeSpec, edgeReac = self.reactionModel.getModelSize()
            coreSpeciesCount.append(coreSpec)
            coreReactionCount.append(coreReac)
            edgeSpeciesCount.append(edgeSpec)
            edgeReactionCount.append(edgeReac)
            execTime.append(time.time() - self.initializationTime)
            logging.info('    Execution time (HH:MM:SS): %s' % (time.strftime("%H:%M:%S", time.gmtime(execTime[-1]))))
            try:
                import psutil
                process = psutil.Process(os.getpid())
                rss, vms = process.get_memory_info()
                memoryUse.append(rss / 1.0e6)
                logging.info('    Memory used: %.2f MB' % (memoryUse[-1]))
            except ImportError:
                memoryUse.append(0.0)
            if os.path.exists(os.path.join(self.outputDirectory,'restart.pkl.gz')):
                restartSize.append(os.path.getsize(os.path.join(self.outputDirectory,'restart.pkl.gz')) / 1.0e6)
                logging.info('    Restart file size: %.2f MB' % (restartSize[-1]))
            else:
                restartSize.append(0.0)
            self.saveExecutionStatistics(execTime, coreSpeciesCount, coreReactionCount, edgeSpeciesCount, edgeReactionCount, memoryUse, restartSize)
            if self.generatePlots:
                self.generateExecutionPlots(execTime, coreSpeciesCount, coreReactionCount, edgeSpeciesCount, edgeReactionCount, memoryUse, restartSize)
    
            logging.info('')
    
            # Consider stopping gracefully if the next iteration might take us
            # past the wall time
            if self.wallTime > 0 and len(execTime) > 1:
                t = execTime[-1]
                dt = execTime[-1] - execTime[-2]
                if t + 3 * dt > self.wallTime:
                    logging.info('MODEL GENERATION TERMINATED')
                    logging.info('')
                    logging.info('There is not enough time to complete the next iteration before the wall time is reached.')
                    logging.info('The output model may be incomplete.')
                    logging.info('')
                    logging.info('The current model core has %s species and %s reactions' % (len(reactionModel.core.species), len(reactionModel.core.reactions)))
                    logging.info('The current model edge has %s species and %s reactions' % (len(reactionModel.edge.species), len(reactionModel.edge.reactions)))
                    return
    
        # Write output file
        logging.info('')
        logging.info('MODEL GENERATION COMPLETED')
        logging.info('')
        coreSpec, coreReac, edgeSpec, edgeReac = self.reactionModel.getModelSize()
        logging.info('The final model core has %s species and %s reactions' % (coreSpec, coreReac))
        logging.info('The final model edge has %s species and %s reactions' % (edgeSpec, edgeReac))
        
        # Log end timestamp
        logging.info('')
        logging.info('RMG execution terminated at ' + time.asctime())
    
    def getGitCommit(self):
        try:
            f = os.popen('git log --format="%H %n %cd" -1')
            lines = []
            for line in f: lines.append(line)
            f.close()
            head = lines[0].strip()
            date = lines[1].strip()
            return head, date
        except IndexError:
            return '', ''
    
    def logHeader(self, level=logging.INFO):
        """
        Output a header containing identifying information about RMG to the log.
        """
    
        logging.log(level, '#################################################')
        logging.log(level, '# RMG - Reaction Mechanism Generator            #')
        logging.log(level, '# Version: 0.1.0 (14 May 2009)                  #')
        logging.log(level, '# Authors: RMG Developers (rmg_dev@mit.edu)     #')
        logging.log(level, '# P.I.:    William H. Green (whgreen@mit.edu)   #')
        logging.log(level, '# Website: http://rmg.sourceforge.net/          #')
        logging.log(level, '#################################################\n')
    
        import os
    
        head, date = self.getGitCommit()
        if head != '' and date != '':
            logging.log(level, 'The current git HEAD is:')
            logging.log(level, '\t%s' % head)
            logging.log(level, '\t%s' % date)
    
        logging.log(level, '')
    
    def makeOutputSubdirectory(self, folder):
        """
        Create a subdirectory `folder` in the output directory. If the folder
        already exists (e.g. from a previous job) its contents are deleted.
        """
        dir = os.path.join(self.outputDirectory, folder)
        if os.path.exists(dir):
            # The directory already exists, so delete it (and all its content!)
            shutil.rmtree(dir)
        os.mkdir(dir)
    
    def loadRestartFile(self, path):
        """
        Load a restart file at `path` on disk.
        """
    
        import cPickle
    
        # Unpickle the reaction model from the specified restart file
        logging.info('Loading previous restart file...')
        f = open(path, 'rb')
        reactionModel = cPickle.load(f)
        f.close()
    
        # A few things still point to the species in the input file, so update
        # those to point to the equivalent species loaded from the restart file
    
        # The termination conversions still point to the old species
        from rmgpy.solver.base import TerminationConversion
        for term in reactionModel.termination:
            if isinstance(term, TerminationConversion):
                term.species, isNew = reactionModel.makeNewSpecies(term.species.molecule[0], term.species.label, term.species.reactive)
    
        # The initial mole fractions in the reaction systems still point to the old species
        for reactionSystem in reactionSystems:
            initialMoleFractions = {}
            for spec0, moleFrac in reactionSystem.initialMoleFractions.iteritems():
                spec, isNew = reactionModel.makeNewSpecies(spec0.molecule[0], spec0.label, spec0.reactive)
                initialMoleFractions[spec] = moleFrac
            reactionSystem.initialMoleFractions = initialMoleFractions
    
        # The reactions and reactionDict still point to the old reaction families
        reactionDict = {}
        for family0 in reactionModel.reactionDict:
    
            # Find the equivalent family in the newly-loaded database
            import rmgpy.data.kinetics
            family = None
            for kineticsDatabase in rmgpy.data.kinetics.kineticsDatabases:
                if isinstance(kineticsDatabase, rmgpy.data.kinetics.KineticsPrimaryDatabase):
                    if kineticsDatabase.label == family0.label:
                        family = kineticsDatabase
                        break
                elif isinstance(kineticsDatabase, rmgpy.data.kinetics.KineticsGroupDatabase):
                    for label, fam in kineticsDatabase.families.iteritems():
                        if fam.label == family0.label:
                            family = fam
                            break
            if family is None:
                raise Exception("Unable to find matching reaction family for %s" % family0.label)
    
            # Update each affected reaction to point to that new family
            # Also use that new family in a duplicate reactionDict
            reactionDict[family] = {}
            for reactant1 in reactionModel.reactionDict[family0]:
                reactionDict[family][reactant1] = {}
                for reactant2 in reactionModel.reactionDict[family0][reactant1]:
                    reactionDict[family][reactant1][reactant2] = []
                    for rxn in reactionModel.reactionDict[family0][reactant1][reactant2]:
                        rxn.family = family
                        rxn.reverse.family = family
                        reactionDict[family][reactant1][reactant2].append(rxn)
    
        # Return the unpickled reaction model
        return reactionModel
    
    def saveRestartFile(self, path, reactionModel, delay=0):
        """
        Save a restart file to `path` on disk containing the contents of the
        provided `reactionModel`. The `delay` parameter is a time in seconds; if
        the restart file is not at least that old, the save is aborted. (Use the
        default value of 0 to force the restart file to be saved.)
        """
        import cPickle
        
        # Saving of a restart file is very slow (likely due to all the Quantity objects)
        # Therefore, to save it less frequently, don't bother if the restart file is less than an hour old
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < delay:
            logging.info('Not saving restart file in this iteration.')
            return
        
        # Pickle the reaction model to the specified file
        # We also compress the restart file to save space (and lower the disk read/write time)
        logging.info('Saving restart file...')
        f = open(path, 'wb')
        cPickle.dump(reactionModel, f, cPickle.HIGHEST_PROTOCOL)
        f.close()
    
    def saveExecutionStatistics(self, execTime, coreSpeciesCount, coreReactionCount,
        edgeSpeciesCount, edgeReactionCount, memoryUse, restartSize):
        """
        Save the statistics of the RMG job to an Excel spreadsheet for easy viewing
        after the run is complete. The statistics are saved to the file
        `statistics.xls` in the output directory. The ``xlwt`` package is used to
        create the spreadsheet file; if this package is not installed, no file is
        saved.
        """
    
        # Attempt to import the xlwt package; return if not installed
        try:
            import xlwt
        except ImportError:
            logging.warning('Package xlwt not found. Unable to save execution statistics.')
            return
    
        # Create workbook and sheet for statistics to be places
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet('Statistics')
    
        # First column is execution time
        sheet.write(0,0,'Execution time (s)')
        for i, etime in enumerate(execTime):
            sheet.write(i+1,0,etime)
    
        # Second column is number of core species
        sheet.write(0,1,'Core species')
        for i, count in enumerate(coreSpeciesCount):
            sheet.write(i+1,1,count)
    
        # Third column is number of core reactions
        sheet.write(0,2,'Core reactions')
        for i, count in enumerate(coreReactionCount):
            sheet.write(i+1,2,count)
    
        # Fourth column is number of edge species
        sheet.write(0,3,'Edge species')
        for i, count in enumerate(edgeSpeciesCount):
            sheet.write(i+1,3,count)
    
        # Fifth column is number of edge reactions
        sheet.write(0,4,'Edge reactions')
        for i, count in enumerate(edgeReactionCount):
            sheet.write(i+1,4,count)
    
        # Sixth column is memory used
        sheet.write(0,5,'Memory used (MB)')
        for i, memory in enumerate(memoryUse):
            sheet.write(i+1,5,memory)
    
        # Seventh column is restart file size
        sheet.write(0,6,'Restart file size (MB)')
        for i, memory in enumerate(restartSize):
            sheet.write(i+1,6,memory)
    
        # Save workbook to file
        fstr = os.path.join(self.outputDirectory, 'statistics.xls')
        workbook.save(fstr)
    
    def generateExecutionPlots(self, execTime, coreSpeciesCount, coreReactionCount,
        edgeSpeciesCount, edgeReactionCount, memoryUse, restartSize):
        """
        Generate a number of plots describing the statistics of the RMG job,
        including the reaction model core and edge size and memory use versus
        execution time. These will be placed in the output directory in the plot/
        folder.
        """
    
        logging.info('Generating plots of execution statistics...')
    
        import matplotlib.pyplot as plt
        fig = plt.figure()
        ax1 = fig.add_subplot(111)
        ax1.semilogx(execTime, coreSpeciesCount, 'o-b')
        ax1.set_xlabel('Execution time (s)')
        ax1.set_ylabel('Number of core species')
        ax2 = ax1.twinx()
        ax2.semilogx(execTime, coreReactionCount, 'o-r')
        ax2.set_ylabel('Number of core reactions')
        plt.savefig(os.path.join(self.outputDirectory, 'plot/coreSize.svg'))
        plt.clf()
    
        fig = plt.figure()
        ax1 = fig.add_subplot(111)
        ax1.loglog(execTime, edgeSpeciesCount, 'o-b')
        ax1.set_xlabel('Execution time (s)')
        ax1.set_ylabel('Number of edge species')
        ax2 = ax1.twinx()
        ax2.loglog(execTime, edgeReactionCount, 'o-r')
        ax2.set_ylabel('Number of edge reactions')
        plt.savefig(os.path.join(self.outputDirectory, 'plot/edgeSize.svg'))
        plt.clf()
    
        fig = plt.figure()
        ax1 = fig.add_subplot(111)
        ax1.semilogx(execTime, memoryUse, 'o-k')
        ax1.semilogx(execTime, restartSize, 'o-g')
        ax1.set_xlabel('Execution time (s)')
        ax1.set_ylabel('Memory (MB)')
        ax1.legend(['RAM', 'Restart file'], loc=2)
        plt.savefig(os.path.join(self.outputDirectory, 'plot/memoryUse.svg'))
        plt.clf()
    
################################################################################

def initializeLog(verbose, log_file_name):
    """
    Set up a logger for RMG to use to print output to stdout. The
    `verbose` parameter is an integer specifying the amount of log text seen
    at the console; the levels correspond to those of the :data:`logging` module.
    """
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(verbose)

    # Create console handler and set level to debug; send everything to stdout
    # rather than stderr
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(verbose)

    logging.addLevelName(logging.CRITICAL, 'Critical: ')
    logging.addLevelName(logging.ERROR, 'Error: ')
    logging.addLevelName(logging.WARNING, 'Warning: ')
    logging.addLevelName(logging.INFO, '')
    logging.addLevelName(logging.DEBUG, '')
    logging.addLevelName(0, '')

    # Create formatter and add to console handler
    #formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S')
    #formatter = Formatter('%(message)s', '%Y-%m-%d %H:%M:%S')
    formatter = logging.Formatter('%(levelname)s%(message)s')
    ch.setFormatter(formatter)

    # create file handler
    if os.path.exists(log_file_name):
        backup_name = '_backup'.join(os.path.splitext(log_file_name))
        if os.path.exists(backup_name):
            print "Removing old file %s" % backup_name
            os.remove(backup_name)
        print "Renaming %s to %s"%(log_file_name, backup_name)
        print
        os.rename(log_file_name, backup_name)
    fh = logging.FileHandler(filename=log_file_name) #, backupCount=3)
    fh.setLevel(min(logging.DEBUG,verbose)) # always at least VERBOSE in the file
    fh.setFormatter(formatter)
    # notice that STDERR does not get saved to the log file
    # so errors from underlying libraries (eg. openbabel) etc. that report
    # on stderr will not be logged to disk.

    # remove old handlers!
    while logger.handlers:
        logger.removeHandler(logger.handlers[0])

    # Add ch to logger
    logger.addHandler(ch)
    logger.addHandler(fh)

################################################################################

class Tee:
    """A simple tee to create a stream which prints to many streams.
    
    This is used to report the profiling statistics to both the log file
    and the standard output.
    """
    def __init__(self, *fileobjects):
        self.fileobjects=fileobjects
    def write(self, string):
        for fileobject in self.fileobjects:
            fileobject.write(string)

def processProfileStats(stats_file, log_file):
    import pstats
    out_stream = Tee(sys.stdout,open(log_file,'a')) # print to screen AND append to RMG.log
    print >>out_stream, "="*80
    print >>out_stream, "Profiling Data".center(80)
    print >>out_stream, "="*80
    stats = pstats.Stats(stats_file,stream=out_stream)
    stats.strip_dirs()
    print >>out_stream, "Sorted by internal time"
    stats.sort_stats('time')
    stats.print_stats(25)
    stats.print_callers(25)
    print >>out_stream, "Sorted by cumulative time"
    stats.sort_stats('cumulative')
    stats.print_stats(25)
    stats.print_callers(25)
    stats.print_callees(25)

def makeProfileGraph(stats_file):
    """
    Uses gprof2dot to create a graphviz dot file of the profiling information.
    
    This requires the gprof2dot package available via `pip install gprof2dot`.
    Render the result using the program 'dot' via a command like
    `dot -Tpdf input.dot -o output.pdf`.
    """
    try:
        from gprof2dot import gprof2dot
    except ImportError:
        logging.warning('Package gprof2dot not found. Unable to create a graph of the profile statistics.')
        # `pip install gprof2dot` if you don't have it.
        return
    import subprocess
    m = gprof2dot.Main()
    class Options:
        pass
    m.options = Options()
    m.options.node_thres = 0.8
    m.options.edge_thres = 0.1
    m.options.strip = False
    m.options.wrap = True
    m.theme = m.themes['color'] # bw color gray pink
    parser = gprof2dot.PstatsParser(stats_file)
    m.profile = parser.parse()
    dot_file = stats_file + '.dot'
    m.output = open(dot_file,'wt')
    m.write_graph()
    m.output.close()
    try:
        subprocess.check_call(['dot', '-Tpdf', dot_file, '-o', '{0}.pdf'.format(dot_file)])
    except subprocess.CalledProcessError:
        logging.error("Error returned by 'dot' when generating graph of the profile statistics.")
        logging.info("To try it yourself:\n     dot -Tpdf {0} -o {0}.pdf".format(dot_file))
    except OSError:
        logging.error("Couldn't run 'dot' to create graph of profile statistics. Check graphviz is installed properly and on your path.")
        logging.info("Once you've got it, try:\n     dot -Tpdf {0} -o {0}.pdf".format(dot_file))
    else:
        logging.info("Graph of profile statistics saved to: \n {0}.pdf".format(dot_file))
    # we could actually try this here using subprocess.Popen() or something
    # wrapped in a try: block.
