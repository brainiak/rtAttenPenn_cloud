function [patterns] = RealTimePunisherFileProcess(subjectNum,runNum, date_pattern)
% function [patterns] = RealTimePunisherFileProcess(subjectNum,subjectName,runNum,fMRI,rtData)
%
% this function describes the file processing procedure for the realtime
% fMRI attentional training experiment
%
%
% REQUIRED INPUTS:
% - imgDirHeader: where to look for the dicom images (the header only)
% - subjectNum:  participant number [any integer]
%                if subjectNum = 0, no information will be saved
% - subjectName: ntblab subject naming convention [MMDDYY#_REALTIME02]
% - runNum:      run number [any integer]
% - fMRI:        whether collecting fMRI data [scannumber if yes/0 if not]
% - rtData:whether data acquired in realtime or previously collected [1/0]
%
% OUTPUTS
% - patterns: elapsed time for each iteration of SVM testing
%
% Written by: Nick Turk-Browne
% Editied by: Megan deBettencourt
% Version: 2.0
% Last modified: 10/14/11

%% Initialize Python
% pyversion
% pyversion /usr/local/bin/python3
%insert(py.sys.path, int32(0), '.')
%rtAttenPy_v0 = py.importlib.import_module('rtAttenPy_v0')
% rtAttenPy_v0 = py.importlib.reload(rtAttenPy_v0)

record_trace_params = 2;
% if record_trace is true then record parameters used so that the trace
% can be reproduced for python testing

%% Boilerplate

seed = sum(100*clock); %get random seed
RandStream.setGlobalStream(RandStream('mt19937ar','seed',seed));%set seed

%initialize system time calls
%GetSecs;


%% Load or Initialize Real-Time Data & Staircasing Parameters

% if matchNum == 0
%     dataHeader = ['data/' num2str(subjectNum)];
%     runHeader = [dataHeader '/run' num2str(runNum)];
%     classOutputDir = [runHeader '/classoutput'];
%     matchDataHeader = ['data/' num2str(subjectNum) '_match'];
%     matchRunHeader = [matchDataHeader '/run' num2str(runNum)];
%     matchClassOutputDir = [matchRunHeader '/classoutput'];
% else
%     dataHeader = ['data/' num2str(matchNum) '_match'];
%     runHeader = [dataHeader '/run' num2str(runNum)];
%     classOutputDir = [runHeader '/controlneverseenclassoutput'];
% end

if runNum >1
    rtfeedback = 1;
else
    rtfeedback = 0;
end

if record_trace_params
    % record parameters
    params.runNum = runNum;
    params.subjectNum = subjectNum;
    params.rtfeedback = rtfeedback;
end

[TopDir,~,~] = fileparts(pwd);
inputDataDir = [TopDir '/data/input'];
outputDataDir = [TopDir '/data/output'];
runDataDir = [TopDir '/data/output/run' num2str(runNum)];
if ~exist(runDataDir)
  mkdir(runDataDir);
end

patternsdesign_fname = char(findNewestFile(inputDataDir, fullfile(inputDataDir, ['patternsdesign_' num2str(runNum) '_' date_pattern '*.mat'])));
curr_pdata_fname = char(findNewestFile(outputDataDir, fullfile(outputDataDir, ['patternsdata_' num2str(runNum) '_' date_pattern '*.mat'])));
prev_pdata_fname = char(findNewestFile(outputDataDir, fullfile(outputDataDir, ['patternsdata_' num2str(runNum-1) '_' date_pattern '*.mat'])));
model_fname = char(findNewestFile(outputDataDir, fullfile(outputDataDir, ['trainedModel_' num2str(runNum-1) '_' date_pattern '*.mat'])));


% This is where patterns variable comes from
load(patternsdesign_fname);
%imgDir = [imgDirHeader datestr(now,10) datestr(now,5) datestr(now,7) '.' subjectName '.' subjectName '/'];

if record_trace_params
    params.patternsdesign_filename = patternsdesign_fname;
end

%%%%%%%%
%DELETE AFTER
%\subjDate = '8-11-17';
%imgDir = [imgDirHeader datestr(subjDate,10) datestr(subjDate,5) datestr(subjDate,7) '.' subjectName '.' subjectName '/'];
%%%%%%%%


%check that the fMRI file directory exists

%check that the fMRI dicom files do NOT exist

%load previous patterns
if runNum>1
    oldpats = load(deblank(prev_pdata_fname));
    % trainedmodel variables loaded here
    load(deblank(model_fname),'trainedModel');
end
% LOAD CURRENT PATTERNS DATA
p = load(deblank(curr_pdata_fname));

if record_trace_params
    params.prev_pdata_filename = prev_pdata_fname;
    params.curr_pdata_filename = curr_pdata_fname;
    params.model_filename = model_fname;
end

%% Experimental Parameters

%scanning parameters
imgmat = 64; % the fMRI image matrix size
temp = load([inputDataDir '/mask_' num2str(subjectNum)]);
roi = temp.mask;
assert(exist('roi','var')==1);
roiDims = size(roi);
roiInds = find(roi);

%pre-processing parameters
FWHM = 5;
cutoff = 112;
%timeOut = TR/2+.25;

zscoreNew = 1;
useHistory = 1;
firstBlockTRs = 64; %total number of TRs to take for standard deviation of last run
%% Block Sequence

firstVolPhase1 = find(patterns.block==1,1,'first'); %#ok<NODEF>
lastVolPhase1 = find(patterns.block==nBlocksPerPhase,1,'last');
nVolsPhase1 = lastVolPhase1 - firstVolPhase1+1;
% WAIT first vol are with any patterns in the block and then lastvolphase2
% is SHIFTED??!?!? or no???
lastVolPhase2 = find(patterns.type~=0,1,'last');
nVolsPhase2 = lastVolPhase2 - firstVolPhase2 + 1;
nVols = size(patterns.block,2);
patterns.fileAvail = zeros(1,nTRs);
patterns.fileNum = NaN(1,nTRs);
patterns.newFile = cell(1,nTRs);
patterns.timeRead = cell(1,nTRs);
patterns.fileload = NaN(1,nTRs);
%patterns.raw = nan(nTRs,numel(roiInds));
patterns.raw = p.patterns.raw;
patterns.raw_sm = nan(nTRs,numel(roiInds));
patterns.raw_sm_filt = nan(nTRs,numel(roiInds));
patterns.raw_sm_filt_z = nan(nTRs,numel(roiInds));
patterns.predict = NaN(1,nTRs);
patterns.categoryseparation = NaN(1,nTRs);
patterns.firstTestTR = find(patterns.regressor(1,:)+patterns.regressor(2,:),1,'first') ; %(because took out first 10)

%% Output Files Setup

% open and set-up output file
dataFile = fopen([runDataDir '/fileprocessing.txt'],'a');
fprintf(dataFile,'\n*********************************************\n');
fprintf(dataFile,'* rtAttenPenn v.1.0\n');
fprintf(dataFile,['* Date/Time: ' datestr(now,0) '\n']);
fprintf(dataFile,['* Seed: ' num2str(seed) '\n']);
fprintf(dataFile,['* Subject Number: ' num2str(subjectNum) '\n']);
fprintf(dataFile,['* Run Number: ' num2str(runNum) '\n']);
%fprintf(dataFile,['* Real-Time Data: ' num2str(rtData) '\n']);
fprintf(dataFile,'*********************************************\n\n');

% print header to command window
fprintf('\n*********************************************\n');
fprintf('* rtAttenPenn v.1.0\n');
fprintf(['* Date/Time: ' datestr(now,0) '\n']);
fprintf(['* Seed: ' num2str(seed) '\n']);
fprintf(['* Subject Number: ' num2str(subjectNum) '\n']);
fprintf(['* Run Number: ' num2str(runNum) '\n']);
%fprintf(dataFile,['* Real-Time Data: ' num2str(rtData) '\n']);
fprintf('*********************************************\n\n');


%% Start Experiment

% prepare for trial sequence
fprintf(dataFile,'run\tblock\ttrial\tbltyp\tblcat\tstim\tfilenum\tloaded\toutput\tavg\n');
fprintf('run\tblock\ttrial\tbltyp\tblcat\tstim\tfilenum\tloaded\toutput\tavg\n');


%% acquiring files

fileCounter = firstVolPhase1-1; %file number = # of TR pulses
for iTrialPhase1 = 1:(firstVolPhase2-1) % (change ACM 8/10/17: keeping this going past the break-no need to break it into separate steps)


    %increase the count of TR pulses
    fileCounter = fileCounter+1; % so fileCounter begins at firstVolPhase1

    %save this into the structure
%     patterns.fileNum(iTrialPhase1) =  fileCounter+disdaqs/TR;
%
%     %check for new files from the scanner
%     patterns.fileAvail(iTrialPhase1) = 0;
%
%     %check for new files from the scanner
%     while (patterns.fileAvail(iTrialPhase1)==0)
%         [patterns.fileAvail(iTrialPhase1) patterns.newFile{iTrialPhase1}] = GetSpecificFMRIFile(imgDir,fMRI,patterns.fileNum(iTrialPhase1));
%     end
%
%     %if desired file is recognized, pause for 200ms to complete transfer
%     pause(.2);
%
%     % if file available, load it
%     if (patterns.fileAvail(iTrialPhase1))
%         [newVol patterns.timeRead{iTrialPhase1}] = ReadFile([imgDir patterns.newFile{iTrialPhase1}],imgmat,roi); % NTB: only reads top file
%         patterns.raw(iTrialPhase1,:) = newVol;  % keep patterns for later training
%
%         if (any(isnan(patterns.raw(iTrialPhase1,:)))) && (iTrialPhase1>1)
%             patterns.fileload(iTrialPhase1) = 0; %mark that load failed
%             indLastValidPattern = find(patterns.fileload,1,'last');
%             patterns.raw(iTrialPhase1,:) = patterns.raw(indLastValidPattern,:); %replicate last complete pattern
%         else
%             patterns.fileload(iTrialPhase1) = 1;
%         end
%
%     end

    %smooth files
    patterns.raw_sm(iTrialPhase1,:) = SmoothRealTime(patterns.raw(iTrialPhase1,:),roiDims,roiInds,FWHM);


    % print trial results
    fprintf(dataFile,'%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%.3f\t%.3f\n',runNum,patterns.block(iTrialPhase1),iTrialPhase1,patterns.type(iTrialPhase1),patterns.attCateg(iTrialPhase1),patterns.stim(iTrialPhase1),patterns.fileNum(iTrialPhase1),patterns.fileAvail(iTrialPhase1),NaN,NaN);
    fprintf('%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%.3f\t%.3f\n',runNum,patterns.block(iTrialPhase1),iTrialPhase1,patterns.type(iTrialPhase1),patterns.attCateg(iTrialPhase1),patterns.stim(iTrialPhase1),patterns.fileNum(iTrialPhase1),patterns.fileAvail(iTrialPhase1),NaN,NaN);

end % Phase1 loop
% fileCounter will be at 115 here
% save('raw_sm.run2.mat', 'patterns.raw_sm')

% quick highpass filter!
fprintf(dataFile,'\n*********************************************\n');
fprintf(dataFile,'beginning highpass filter/zscore...\n');
fprintf('\n*********************************************\n');
fprintf('beginning highpassfilter/zscore...\n');
%p1 = GetSecs;
i1 = 1;
i2 = firstVolPhase2-1;
patterns.raw_sm_filt(i1:i2,:) = HighPassBetweenRuns(patterns.raw_sm(i1:i2,:),TR,cutoff);
patterns.phase1Mean(1,:) = mean(patterns.raw_sm_filt(i1:i2,:),1);
patterns.phase1Y(1,:) = mean(patterns.raw_sm_filt(i1:i2,:).^2,1);
patterns.phase1Std(1,:) = std(patterns.raw_sm_filt(i1:i2,:),[],1);
patterns.phase1Var(1,:) = patterns.phase1Std(1,:).^2;
patterns.raw_sm_filt_z(i1:i2,:) = (patterns.raw_sm_filt(i1:i2,:) - repmat(patterns.phase1Mean,size(patterns.raw_sm_filt(i1:i2,:),1),1))./repmat(patterns.phase1Std,size(patterns.raw_sm_filt(i1:i2,:),1),1);
%p2 = GetSecs;
%fprintf(dataFile,sprintf('elapsed time...%.4f seconds\n',p2-p1));
%fprintf(sprintf('elapsed time...%.4f seconds\n',p2-p1));

%% testing
fprintf(dataFile,'\n*********************************************\n');
fprintf(dataFile,'beginning model testing...\n');
fprintf('\n*********************************************\n');
fprintf('beginning model testing...\n');

% prepare for trial sequence
fprintf(dataFile,'run\tblock\ttrial\tbltyp\tblcat\tstim\tfilenum\tloaded\toutput\tavg\n');
fprintf('run\tblock\ttrial\tbltyp\tblcat\tstim\tfilenum\tloaded\tpredict\toutput\tavg\n');

for iTrialPhase2=firstVolPhase2:nVols
    zscoreLen = double(iTrialPhase2);
    zscoreLen1 = double(iTrialPhase2 - 1);
    zscoreConst = 1.0/zscoreLen;
    zscoreConst1 = 1.0/zscoreLen1;

    fileCounter = fileCounter+1;

    patterns.fileNum(iTrialPhase2) = fileCounter+disdaqs/TR;

    %check for new files from the scanner
%     patterns.fileAvail(iTrialPhase2) = 0;
%     while (patterns.fileAvail(iTrialPhase2)==0)
%         [patterns.fileAvail(iTrialPhase2) patterns.newFile{iTrialPhase2}] = GetSpecificFMRIFile(imgDir,fMRI,patterns.fileNum(fileCounter));
%     end

    % if file available, perform preprocessing and test classifier
    %if (patterns.fileAvail(iTrialPhase2))

        %pause(.2);

        %[newVol patterns.timeRead{iTrialPhase2}] = ReadFile([imgDir patterns.newFile{iTrialPhase2}],imgmat,roi);
        %patterns.raw(iTrialPhase2,:) = newVol;  % keep patterns for later training

%         if (any(isnan(patterns.raw(iTrialPhase2,:))))
%             patterns.fileload(iTrialPhase2) = 0;
%             indLastValidPatterns = find(patterns.fileload,1,'last');
%             patterns.raw(iTrialPhase2,:) = patterns.raw(indLastValidPattern,:); %replicate last complete pattern
%         else
%             patterns.fileload(iTrialPhase2) = 1;
%         end

        %smooth
        patterns.raw_sm(iTrialPhase2,:) = SmoothRealTime(patterns.raw(iTrialPhase2,:),roiDims,roiInds,FWHM);

        %z-score
%     else
%         patterns.fileload(iTrialPhase2) = 0;
%         indLastValidPatterns = find(patterns.fileload,1,'last');
%         patterns.raw_sm_filt(iTrialPhase2,:) = patterns.raw_sm_filt(indLastValidPatterns,:);
%     end


    % detrend
    patterns.raw_sm_filt(iTrialPhase2,:) = HighPassRealTime(patterns.raw_sm(1:iTrialPhase2,:),TR,cutoff);

    % only update if the latest file wasn't nan
    %if patterns.fileload(iTrialPhase2)

    patterns.raw_sm_filt_z(iTrialPhase2,:) = (patterns.raw_sm_filt(iTrialPhase2,:) - patterns.phase1Mean(1,:))./patterns.phase1Std(1,:);

    if rtfeedback
        if any(patterns.regressor(:,iTrialPhase2))
            [patterns.predict(iTrialPhase2),~,~,patterns.activations(:,iTrialPhase2)] = Test_L2_RLR_realtime(trainedModel,patterns.raw_sm_filt_z(iTrialPhase2,:),patterns.regressor(:,iTrialPhase2)); %#ok<NODEF>

            categ = find(patterns.regressor(:,iTrialPhase2));
            otherCateg = mod(categ,2)+1;
            patterns.categoryseparation(iTrialPhase2) = patterns.activations(categ,iTrialPhase2)-patterns.activations(otherCateg,iTrialPhase2);

            classOutput = patterns.categoryseparation(iTrialPhase2); %#ok<NASGU>
            save([runDataDir '/vol_' num2str(patterns.fileNum(iTrialPhase2))],'classOutput');
        else
            patterns.categoryseparation(iTrialPhase2) = NaN;

            classOutput = patterns.categoryseparation(iTrialPhase2); %#ok<NASGU>

            save([runDataDir '/vol_' num2str(patterns.fileNum(iTrialPhase2))],'classOutput');
        end
    else
        patterns.categoryseparation(iTrialPhase2) = NaN;
    end

    % print trial results
    fprintf(dataFile,'%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%.3f\t%.3f\n',runNum,patterns.block(iTrialPhase2),iTrialPhase2,patterns.type(iTrialPhase2),patterns.attCateg(iTrialPhase2),patterns.stim(iTrialPhase2),patterns.fileNum(iTrialPhase2),patterns.fileAvail(iTrialPhase2),patterns.categoryseparation(iTrialPhase2),nanmean(patterns.categoryseparation(firstVolPhase2:iTrialPhase2)));
    fprintf('%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%.3f\t%.3f\n',runNum,patterns.block(iTrialPhase2),iTrialPhase2,patterns.type(iTrialPhase2),patterns.attCateg(iTrialPhase2),patterns.stim(iTrialPhase2),patterns.fileNum(iTrialPhase2),patterns.fileAvail(iTrialPhase2),patterns.predict(iTrialPhase2), patterns.categoryseparation(iTrialPhase2),nanmean(patterns.categoryseparation(firstVolPhase2:iTrialPhase2)));


end % Phase 2 loop

patterns.runStd = nanstd(patterns.raw_sm_filt,[],1); %std dev across all volumes per voxel

%% training
trainStart = tic; %start timing

%print training results
fprintf(dataFile,'\n*********************************************\n');
fprintf(dataFile,'beginning model training...\n');
fprintf('\n*********************************************\n');
fprintf('beginning model training...\n');

%model training
% we have to specify which TR's are correct for first 4 blocks and second
% four blocks
% last volPhase1 and first volPhase1/2 are NOT shifted though!!
i_phase1 = 1:lastVolPhase1+2;
i_phase2 = firstVolPhase2:nVols;
%any(patterns.regressor(:,i_phase2),1)
if runNum == 1
    % for the first run, we're going to train on first and second part of
    % run 1
    trainIdx1 = find(any(patterns.regressor(:,i_phase1),1));
    trainLabels1 = patterns.regressor(:,trainIdx1)'; %find the labels of those indices
    trainPats1 = patterns.raw_sm_filt_z(trainIdx1,:); %retrieve the patterns of those indices

    trainIdx2 = find(any(patterns.regressor(:,i_phase2),1));
    trainLabels2 = patterns.regressor(:,(firstVolPhase2-1)+trainIdx2)'; %find the labels of those indices
    trainPats2 = patterns.raw_sm_filt_z((firstVolPhase2-1)+trainIdx2,:);
elseif runNum == 2
    % take last run from run 1 and first run from run 2
    trainIdx1 = find(any(oldpats.patterns.regressor(:,i_phase2),1));
    trainLabels1 = oldpats.patterns.regressor(:,(firstVolPhase2-1)+trainIdx1)'; %find the labels of those indices
    trainPats1 = oldpats.patterns.raw_sm_filt_z((firstVolPhase2-1)+trainIdx1,:);

    trainIdx2 = find(any(patterns.regressor(:,i_phase1),1));
    trainLabels2 = patterns.regressor(:,trainIdx2)'; %find the labels of those indices
    trainPats2 = patterns.raw_sm_filt_z(trainIdx2,:); %retrieve the patterns of those indices
else
    % take previous 2 first parts
    trainIdx1 = find(any(oldpats.patterns.regressor(:,i_phase1),1));
    trainLabels1 = oldpats.patterns.regressor(:,trainIdx1)'; %find the labels of those indices
    trainPats1 = oldpats.patterns.raw_sm_filt_z(trainIdx1,:); %retrieve the patterns of those indices

    trainIdx2 = find(any(patterns.regressor(:,i_phase1),1));
    trainLabels2 = patterns.regressor(:,trainIdx2)'; %find the labels of those indices
    trainPats2 = patterns.raw_sm_filt_z(trainIdx2,:); %retrieve the patterns of those indices
end

trainPats = [trainPats1;trainPats2];
trainLabels = [trainLabels1;trainLabels2];

trainedModel = classifierLogisticRegression(trainPats,trainLabels); %train the model

trainingOnlyTime = toc(trainStart);  %end timing

%print training timing and results

fprintf(dataFile,'model training time: \t%.3f\n',trainingOnlyTime);
fprintf('model training time: \t%.3f\n',trainingOnlyTime);
if isfield(trainedModel,'biases')
    fprintf(dataFile,'model biases: \t%.3f\t%.3f\n',trainedModel.biases(1),trainedModel.biases(2));
    fprintf('model biases: \t%.3f\t%.3f\n',trainedModel.biases(1),trainedModel.biases(2));
end

%%
% TODO - if datepattern is set, then use that for the output files also
output_patterns_fn = [outputDataDir '/patternsdata_' num2str(runNum) '_' date_pattern '_' datestr(now,"HHMM")];
output_trainedModel_fn = [outputDataDir '/trainedModel_' num2str(runNum) '_' date_pattern '_' datestr(now,"HHMM")];
save(output_patterns_fn,'patterns');
save(output_trainedModel_fn,'trainedModel','trainPats','trainLabels');

if record_trace_params == 2
    params.result_patterns_filename = output_patterns_fn;
    params.result_model_filename = output_trainedModel_fn;
    save([outputDataDir '/trace_params_run' num2str(runNum) '_' datestr(now, 30)], 'params');
end

% clean up and go home
fclose('all');
%end
